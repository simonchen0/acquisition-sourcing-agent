import hashlib
import json
import time
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from .db import Session, User, Job, Usage, Target, Cache, Document, Evaluation
from . import config
from .criteria import Criteria, screen
from .discovery import BraveProvider, queries, normalize, canonical_url, cache_key, TransientProviderError
from .documents import extract, read_document
from .evaluation import analyze, estimated_request_cost
from .providers import ProviderThrottled

ACTIVE = ['queued','running','retrying']
LEASE_SECONDS = 300


def month(): return datetime.now(timezone.utc).strftime('%Y-%m')


def enqueue(db, user, kind, payload, key, budget):
    existing = db.scalar(select(Job).where(Job.user_id==user.id, Job.idempotency_key==key))
    if existing: return existing
    fingerprint = hashlib.sha256(json.dumps({'kind':kind,'payload':payload},sort_keys=True).encode()).hexdigest()
    # Serializable user-row update prevents duplicate active submissions across API processes.
    db.execute(update(User).where(User.id==user.id).values(spend=User.spend))
    active = db.scalars(select(Job).where(Job.user_id==user.id,Job.kind==kind,Job.status.in_(ACTIVE))).all()
    for job in active:
        if job.payload.get('_fingerprint')==fingerprint: return job
    payload = {**payload,'_fingerprint':fingerprint}
    job = Job(user_id=user.id,kind=kind,payload=payload,idempotency_key=key,budget=budget)
    db.add(job); db.commit()
    return job


def reserve(db, job, cost, provider, category):
    """Reserve BEFORE each request; ambiguous failures remain charged conservatively."""
    import math
    if not math.isfinite(cost) or cost<0: raise ValueError('Invalid cost reservation.')
    user = db.get(User,job.user_id)
    cap = float(user.settings.get('monthly_budget',config.DEFAULT_MONTHLY_BUDGET))
    db.execute(update(User).where(User.id==user.id, User.month!=month()).values(month=month(),spend=0))
    if job.spent+cost>job.budget+1e-9: raise ValueError('Per-job spending limit reached. Results have been preserved.')
    result = db.execute(update(User).where(User.id==user.id,User.spend+cost<=cap).values(spend=User.spend+cost))
    if not result.rowcount: raise ValueError('Monthly spending limit reached. Results have been preserved.')
    job.spent += cost
    db.add(Usage(user_id=job.user_id,job_id=job.id,provider=provider,category=category,estimated_cost=cost,detail={'status':'Reserved maximum/estimated cost; provider billing is authoritative'}))
    db.commit()


def claim(db):
    now = time.time()
    ids = db.scalars(select(Job.id).where(((Job.status.in_(['queued','retrying'])) & (Job.lease<=now)) | ((Job.status=='running') & (Job.lease<now))).order_by(Job.id).limit(20)).all()
    for jid in ids:
        result = db.execute(update(Job).where(Job.id==jid, Job.lease<=now, Job.status.in_(ACTIVE)).values(status='running',lease=now+LEASE_SECONDS))
        db.commit()
        if result.rowcount: return db.get(Job,jid)
    return None


def counts(db,job,category):
    all_targets = db.scalars(select(Target).where(Target.job_id==job.id,Target.category==category)).all()
    c = Criteria.model_validate(job.payload['criteria'])
    eligible = [t for t in all_targets if t.data.get('_apollo_stage') in (None,'complete') and t.screening.get('tier')!='Likely out of range' and (t.screening['status']=='Matches Known Criteria' or (c.include_verification and t.screening['status']=='Needs Verification'))]
    return len(eligible)


def run_brave_sourcing(db,job):
    c = Criteria.model_validate(job.payload['criteria'])
    steps = queries(c.model_dump())
    # Round-robin categories avoids consuming a 'both' job entirely on brokered queries.
    categories = sorted(set(s['category'] for s in steps))
    groups = [[s for s in steps if s['category']==cat] for cat in categories]
    steps = [g[i] for i in range(max(map(len,groups))) for g in groups if i<len(g)]
    provider = BraveProvider()
    for idx in range(job.cursor,len(steps)):
        db.refresh(job)
        if job.cancel: job.status='cancelled'; job.lease=0; db.commit(); return
        step = steps[idx]
        if counts(db,job,step['category'])>=c.target_count:
            job.cursor=idx+1; db.commit(); continue
        key = cache_key(job.user_id,step)
        cached = db.get(Cache,key)
        if cached and time.time()-cached.created<3600: response = cached.data
        else:
            if not config.BRAVE_KEY or not config.BRAVE_STORAGE_RIGHTS: raise ValueError('Brave Search needs a key and a plan permitting storage. Configure BRAVE_SEARCH_API_KEY and BRAVE_STORAGE_RIGHTS_CONFIRMED. No request was made.')
            reserve(db,job,config.BRAVE_REQUEST_COST,'Brave Search','sourcing')
            response = provider.search(step['query'],step['offset'])
            if cached: cached.data=response; cached.created=time.time()
            else: db.add(Cache(key=key,user_id=job.user_id,data=response))
            db.commit()
        for result in response.get('web',{}).get('results',[]):
            data = normalize(result,step['category'],step['query'])
            if not data: continue
            identity = canonical_url(data['url'],step['category'])
            existing = db.scalar(select(Target).where(Target.job_id==job.id,Target.category==step['category'],Target.identity==identity))
            if existing:
                merged = dict(existing.data)
                merged['evidence'] = (merged.get('evidence',[])+data.get('evidence',[]))[:30]
                merged['facts'] = {**data.get('facts',{}),**merged.get('facts',{})}
                known = merged.get('contacts',[])
                merged['contacts'] = known+[v for v in data.get('contacts',[]) if v not in known]
                existing.data=merged; existing.screening=screen(merged,c)
            elif counts(db,job,step['category'])<c.target_count:
                data['last_researched']=datetime.now(timezone.utc).isoformat()
                db.add(Target(user_id=job.user_id,job_id=job.id,category=step['category'],identity=identity,data=data,screening=screen(data,c)))
            db.flush()
        job.cursor=idx+1; job.attempts=0; job.lease=time.time()+LEASE_SECONDS
        job.progress={cat:counts(db,job,cat) for cat in categories}
        db.commit()
        if all(counts(db,job,cat)>=c.target_count for cat in categories): break
    job.status='completed' if all(counts(db,job,cat)>=c.target_count for cat in categories) else 'incomplete'
    job.error=None if job.status=='completed' else 'Available queries yielded fewer eligible candidates than requested. No mandatory filters were relaxed.'
    job.lease=0; db.commit()


def run_evaluation(db,job):
    existing = db.scalar(select(Evaluation).where(Evaluation.job_id==job.id))
    if existing: job.status='completed'; job.lease=0; db.commit(); return
    if not config.AI_KEY: raise ValueError('AI integration is unavailable: configure AI_API_KEY or OPENAI_API_KEY. No request was made.')
    chunks = []
    for did in job.payload['document_ids']:
        document = db.scalar(select(Document).where(Document.id==did,Document.user_id==job.user_id,Document.opportunity_id==job.payload['opportunity_id']))
        if not document: raise ValueError('An evaluation document was deleted. Submit a new evaluation with available materials.')
        for chunk in extract(document.filename,read_document(document)):
            chunks.append({'document':f'{document.id}:{document.filename}',**chunk})
    if job.payload['notes']: chunks.append({'document':'User notes','location':'notes','text':job.payload['notes']})
    if job.payload['financials']: chunks.append({'document':'Reviewed financials','location':'structured inputs','text':json.dumps(job.payload['financials'])})
    if not chunks: raise ValueError('No text or financial information available. Upload documents or provide detailed notes.')
    if sum(len(c['text'])+len(c['location'])+len(c['document'])+25 for c in chunks)>config.MAX_AI_CHARS: raise ValueError('Evaluation materials exceed 80,000 characters. Reduce the materials; no AI request made.')
    db.refresh(job)
    if job.cancel: job.status='cancelled'; job.lease=0; db.commit(); return
    estimate = estimated_request_cost(chunks,job.payload)
    if estimate>job.budget: raise ValueError(f'Conservative AI cost estimate ${estimate:.3f} exceeds approved budget ${job.budget:.2f}.')
    reserve(db,job,estimate,'OpenAI','ai_evaluation')
    report,usage = analyze(chunks,job.payload)
    report['provider_usage']=usage; report['criteria_snapshot']=job.payload['criteria']; report['materials']=[{'document':c['document'],'location':c['location']} for c in chunks]
    db.refresh(job)
    if job.cancel: job.status='cancelled'; job.lease=0; db.commit(); return
    db.add(Evaluation(user_id=job.user_id,opportunity_id=job.payload['opportunity_id'],job_id=job.id,report=report))
    job.status='completed'; job.lease=0; job.progress={'evaluation':'Complete'}; db.commit()


def run_sourcing(db,job):
    provider=job.payload.get('proprietary_provider')
    # Old queued jobs retain their original Brave contract when Apollo is later enabled.
    if provider=='apollo':
        from .pipeline import run_pipeline
        return run_pipeline(db,job)
    return run_brave_sourcing(db,job)


def tick():
    with Session() as db:
        job = claim(db)
        if not job: return False
        try:
            if job.cancel: job.status='cancelled'; job.lease=0; db.commit(); return True
            if job.kind=='sourcing':run_sourcing(db,job)
            elif job.kind=='evaluation':run_evaluation(db,job)
            elif job.kind=='contact_reveal':
                from .pipeline import run_contact_reveal
                run_contact_reveal(db,job)
            else:raise ValueError('Unknown job kind.')
        except ProviderThrottled as exc:
            db.rollback();job=db.get(Job,job.id);job.status='retrying';job.error=str(exc);job.lease=time.time()+exc.retry_after;db.commit()
        except TransientProviderError as exc:
            db.rollback(); job=db.get(Job,job.id); job.attempts+=1; job.error=str(exc)
            job.status='retrying' if job.attempts<3 else 'failed'; job.lease=time.time()+min(2**job.attempts*5,60) if job.status=='retrying' else 0
            db.commit()
        except Exception as exc:
            jid=job.id; db.rollback(); job=db.get(Job,jid)
            job.status='failed'; job.lease=0
            # Provider response bodies and secrets never appear in error messages.
            job.error=str(exc)[:500] if isinstance(exc,ValueError) else f'{type(exc).__name__}: operation failed; inspect server diagnostics without logging confidential materials.'
            db.commit()
        return True

