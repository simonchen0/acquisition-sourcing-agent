"""Durable Apollo/Brave pipeline. Every unit of work checkpoints before moving on."""
import copy
import hashlib
import json
import math
import time
from sqlalchemy import select, update, case
from sqlalchemy.exc import IntegrityError
from . import config
from .apollo import ApolloProvider, build_org_filters, normalize_org, normalize_people, independent, require_config
from .criteria import Criteria, screen
from .db import Cache, Target, Usage, ProviderRate
from .discovery import BraveProvider, queries, normalize, canonical_url, cache_key
from .providers import ProviderThrottled, ProviderUnavailable


def provider_rate(db):
    # One global credential can serve many accounts/processes. Never store its raw value.
    key=hashlib.sha256(('apollo:'+config.APOLLO_KEY).encode()).hexdigest()
    now=time.time()
    record=db.get(ProviderRate,key)
    if not record:
        try:
            db.add(ProviderRate(key=key,next_allowed=0,window_start=now,calls=0));db.commit()
        except IntegrityError:db.rollback()
    expired=ProviderRate.window_start<=now-3600
    updated=db.execute(update(ProviderRate).where(ProviderRate.key==key,ProviderRate.next_allowed<=now,(expired | (ProviderRate.calls<config.APOLLO_CALLS_PER_HOUR))).values(next_allowed=now+max(6,config.APOLLO_PER_SECOND),window_start=case((expired,now),else_=ProviderRate.window_start),calls=case((expired,1),else_=ProviderRate.calls+1)))
    if not updated.rowcount:
        db.rollback();record=db.get(ProviderRate,key)
        delay=max(1,record.next_allowed-now)
        if record.calls>=config.APOLLO_CALLS_PER_HOUR:delay=max(delay,record.window_start+3600-now)
        raise ProviderThrottled('Apollo request pacing is active; this step will resume automatically without reserving another credit yet.',delay)


def apollo_call(db,job,operation,args,credits,category='proprietary'):
    from .jobs import reserve
    require_config()
    key=cache_key(job.user_id,{'provider':'Apollo','operation':operation,'args':args})
    cached=db.get(Cache,key)
    if cached and time.time()-cached.created<3600:return cached.data
    provider_rate(db)
    # The transaction containing the rate slot is committed by reserve, before HTTP.
    reserve(db,job,credits*config.APOLLO_CREDIT_COST,'Apollo','contact_enrichment' if operation=='reveal' else 'sourcing')
    provider=ApolloProvider()
    response=getattr(provider,operation)(**args)
    if cached:cached.data=response;cached.created=time.time()
    else:db.add(Cache(key=key,user_id=job.user_id,data=response))
    usage=db.scalar(select(Usage).where(Usage.job_id==job.id,Usage.provider=='Apollo').order_by(Usage.id.desc()))
    if usage:usage.detail={**usage.detail,'operation':operation,'credits_reserved':credits,'sourcing_category':category,'response_received':True}
    db.commit()
    return response


def store_target(db,job,category,data,criteria):
    identity=canonical_url(data['url'],category)
    existing=db.scalar(select(Target).where(Target.job_id==job.id,Target.category==category,Target.identity==identity))
    if existing:
        prior=existing.data
        merged={**prior,**data}
        merged['facts']={**prior.get('facts',{}),**data.get('facts',{})}
        for key,fact in prior.get('facts',{}).items():
            if fact.get('status')=='verified':merged['facts'][key]=fact
        merged['contacts']=prior.get('contacts',[])+[c for c in data.get('contacts',[]) if c not in prior.get('contacts',[])]
        merged['evidence']=(prior.get('evidence',[])+data.get('evidence',[]))[-30:]
        existing.data=merged;existing.screening=screen(merged,criteria)
        return existing,False
    target=Target(user_id=job.user_id,job_id=job.id,category=category,identity=identity,data=data,screening=screen(data,criteria))
    db.add(target);db.flush();return target,True


def run_pipeline(db,job):
    from .jobs import counts, reserve, LEASE_SECONDS
    c=Criteria.model_validate(job.payload['criteria'])
    if '_pipeline' not in job.payload:
        queues={}
        if c.mode in ['brokered','both']:queues['brokered']=[{'op':'brave',**step} for step in queries(c.model_dump()) if step['category']=='brokered']
        if c.mode in ['proprietary','both']:queues['proprietary']=[{'op':'search','page':1}]
        job.payload={**job.payload,'_pipeline':{'queues':queues,'turn':0,'warnings':[],'enriched_count':0}}
        db.commit()
    state=copy.deepcopy(job.payload['_pipeline'])
    categories=list(state['queues'])
    while any(state['queues'].values()):
        db.refresh(job)
        if job.cancel:job.status='cancelled';job.lease=0;db.commit();return
        category=categories[state['turn']%len(categories)]
        state['turn']+=1
        queue=state['queues'][category]
        if not queue:continue
        if counts(db,job,category)>=c.target_count:
            state['queues'][category]=[];continue
        task=queue[0]
        if task['op']=='brave':
            key=cache_key(job.user_id,{k:v for k,v in task.items() if k!='op'})
            cached=db.get(Cache,key)
            if cached and time.time()-cached.created<3600:response=cached.data
            else:
                if not config.BRAVE_KEY or not config.BRAVE_STORAGE_RIGHTS:raise ProviderUnavailable('Brokered sourcing requires Brave credentials and storage rights. Apollo proprietary progress has been retained.')
                reserve(db,job,config.BRAVE_REQUEST_COST,'Brave Search','sourcing')
                response=BraveProvider().search(task['query'],task['offset'])
                if cached:cached.data=response;cached.created=time.time()
                else:db.add(Cache(key=key,user_id=job.user_id,data=response))
            for result in response.get('web',{}).get('results',[]):
                if counts(db,job,category)>=c.target_count:break
                data=normalize(result,'brokered',task['query'])
                if data:store_target(db,job,category,data,c)
        elif task['op']=='search':
            response=apollo_call(db,job,'search',{'filters':build_org_filters(c),'page':task['page']},config.APOLLO_SEARCH_CREDITS)
            orgs=response.get('organizations',[])
            remaining=min(c.target_count-counts(db,job,'proprietary'),c.target_count-state.get('enriched_count',0))
            pending=0
            for org in orgs:
                # Public companies and subsidiaries never incur enrichment credits.
                if not independent(org)[0]:continue
                data=normalize_org(org)
                if not data:continue
                existing=db.scalar(select(Target.id).where(Target.job_id==job.id,Target.category=='proprietary',Target.identity==canonical_url(data['url'],'proprietary')))
                if existing:continue
                data['_apollo_stage']='pending'
                target,created=store_target(db,job,'proprietary',data,c)
                if not created or target.screening['tier'] in ['Excluded','Likely out of range']:continue
                if remaining<=0:break
                queue.append({'op':'enrich','target_id':target.id})
                pending+=1
                if pending>=remaining:break
            pagination=response.get('pagination') or {}
            total_pages=pagination.get('total_pages')
            more=bool(orgs) and (task['page']<int(total_pages) if total_pages is not None else len(orgs)>=100)
            if more and pending<remaining and task['page']<math.ceil(c.target_count/100)*3:queue.append({'op':'search','page':task['page']+1})
        elif task['op']=='enrich':
            target=db.get(Target,task['target_id'])
            if not target or target.user_id!=job.user_id or target.job_id!=job.id:raise ValueError('Sourcing target no longer exists.')
            response=apollo_call(db,job,'enrich',{'domain':target.data['primary_domain']},config.APOLLO_ENRICH_CREDITS)
            org=response['organization'];data=normalize_org(org)
            if not data or data['primary_domain']!=target.data['primary_domain']:raise ValueError('Apollo enrichment returned a different company domain; no attributes were attached to this target.')
            state['enriched_count']=state.get('enriched_count',0)+1
            data['_apollo_stage']='enriched'
            target,_=store_target(db,job,'proprietary',data,c)
            if target.screening['tier'] not in ['Excluded','Likely out of range']:queue.insert(1,{'op':'people','target_id':target.id})
            else:target.data={**target.data,'_apollo_stage':'complete'}
        elif task['op']=='people':
            target=db.get(Target,task['target_id'])
            if not target or target.user_id!=job.user_id or target.job_id!=job.id:raise ValueError('Sourcing target no longer exists.')
            response=apollo_call(db,job,'people',{'org_id':target.data['apollo_id']},0)
            contacts=normalize_people(response,target.data['apollo_url'])
            target.data={**target.data,'contacts':target.data.get('contacts',[])+contacts,'_apollo_stage':'complete'}
        else:raise ValueError('Unknown sourcing pipeline operation.')
        queue.pop(0)
        job.cursor+=1;job.attempts=0;job.lease=time.time()+LEASE_SECONDS
        job.payload={**job.payload,'_pipeline':copy.deepcopy(state)}
        db.flush()
        job.progress={cat:counts(db,job,cat) for cat in categories}
        db.commit()
    complete=all(counts(db,job,cat)>=c.target_count for cat in categories)
    job.status='completed' if complete else 'incomplete'
    job.error=None if complete else 'Fewer eligible candidates than requested were available within the supported queries. Mandatory criteria were preserved.'
    job.lease=0;db.commit()


def run_contact_reveal(db,job):
    from .jobs import LEASE_SECONDS
    target=db.get(Target,job.payload['target_id'])
    if not target or target.user_id!=job.user_id:raise ValueError('Company not found.')
    person_id=job.payload['person_id']
    contact=next((c for c in target.data.get('contacts',[]) if c.get('apollo_person_id')==person_id),None)
    if not contact:raise ValueError('Contact was not returned for this company.')
    if contact.get('revealed'):
        job.status='completed';job.lease=0;db.commit();return
    response=apollo_call(db,job,'reveal',{'person_id':person_id},config.APOLLO_REVEAL_CREDITS)
    person=response['person']
    if person.get('id')!=person_id:raise ValueError('Apollo returned a different person; no contact details were attached.')
    db.refresh(job)
    if job.cancel:job.status='cancelled';job.lease=0;db.commit();return
    replacement={**contact,'name':person.get('name') or contact.get('name'),'email':person.get('email'),'email_status':person.get('email_status'),'revealed':True,'verification':'Apollo revealed email; provider status: '+str(person.get('email_status') or 'unverified')}
    target.data={**target.data,'contacts':[replacement if c.get('apollo_person_id')==person_id else c for c in target.data.get('contacts',[])]}
    job.status='completed';job.progress={'contact_reveal':'Complete; no phone/personal-email reveal requested'};job.lease=0;db.commit()
