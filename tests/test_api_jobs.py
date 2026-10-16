import hashlib
import time
import pytest
from sqlalchemy import select,func
from app import config
from app.db import Session,User,Job,Target,Opportunity,Document,Evaluation,Usage
from app.criteria import Criteria
from app.jobs import enqueue,tick
from app.evaluation import FRAMEWORKS
from app.security import hash_password
from app.discovery import normalize

def save_criteria(client):return client.post('/api/criteria',json=Criteria().model_dump()).json()['id']
def standalone(client,name='Example opportunity'):
    response=client.post('/api/opportunities',json={'name':name,'category':'proprietary'});assert response.status_code==200;return response.json()['id']

def test_authentication_csrf_and_pages(client):
    for p in ['/','/find','/deals/brokered','/deals/proprietary','/evaluate','/saved','/settings']:
        r=client.get(p);assert r.status_code==200 and "script-src 'self'" in r.headers['content-security-policy']
    csrf=client.headers.pop('X-CSRF-Token');assert client.post('/api/criteria',json=Criteria().model_dump()).status_code==403
    client.headers['X-CSRF-Token']=csrf;assert client.get('/health').json()['database']=='connected'

def test_save_reload_and_tenant_isolation(client,user):
    cid=save_criteria(client);assert client.get('/api/bootstrap').json()['criteria'][0]['id']==cid
    with Session() as db:
        other=User(email='other@example.com',password=hash_password('other-password-123'));db.add(other);db.flush()
        o=Opportunity(user_id=other.id,name='Private deal',category='brokered');db.add(o);db.commit();oid=o.id
    assert client.get('/api/opportunities/'+str(oid)).status_code==404
    assert client.put('/api/opportunities/'+str(oid),json={'notes':'Intrusion'}).status_code==404

def test_unavailable_integrations_reported_honestly(client,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','');monkeypatch.setattr(config,'AI_KEY','')
    assert client.post('/api/search',json={'criteria':Criteria().model_dump(),'budget':1,'idempotency_key':'test-key-1'}).status_code==409
    oid=standalone(client);assert client.post(f'/api/opportunities/{oid}/evaluate',json={'budget':.25,'idempotency_key':'test-key-2'}).status_code==409
    assert client.get('/api/jobs').json()==[]

def test_upload_does_not_extract_or_evaluate_and_deletion(client,monkeypatch):
    oid=standalone(client)
    def forbidden(*_):raise AssertionError('Upload must not extract.')
    monkeypatch.setattr('app.main.extract',forbidden)
    r=client.post(f'/api/opportunities/{oid}/documents',files={'file':('financials.txt',b'Revenue 1200000','text/plain')});assert r.status_code==200;did=r.json()['id']
    with Session() as db:
        d=db.get(Document,did);assert b'Revenue' not in (config.DATA/'documents'/d.storage).read_bytes();assert db.scalar(select(func.count()).select_from(Evaluation))==0
    assert client.get('/api/jobs').json()==[]
    assert client.delete('/api/documents/'+str(did)).status_code==200
    assert client.get(f'/api/opportunities/{oid}').json()['documents']==[]

def test_bad_file_and_explicit_preview(client):
    oid=standalone(client)
    assert client.post(f'/api/opportunities/{oid}/documents',files={'file':('bad.exe',b'bad')}).status_code==400
    d=client.post(f'/api/opportunities/{oid}/documents',files={'file':('notes.csv',b'year,revenue\n2025,1200000')}).json()
    preview=client.post('/api/documents/'+str(d['id'])+'/preview');assert preview.json()['chunks'][1]['text']=='2025 | 1200000'

def test_background_sourcing_both_dedup_and_no_scoring(client,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','fixture')
    steps=[{'category':'brokered','query':'sale','offset':0},{'category':'proprietary','query':'company','offset':0}]
    monkeypatch.setattr('app.jobs.queries',lambda _:steps)
    def search(self,query,offset=0):
        if query=='sale':return {'web':{'results':[{'title':'Business for sale','url':'https://broker.example/listing/1','description':'Revenue: $5M'},{'title':'Business for sale','url':'https://broker.example/listing/1?utm_source=other','description':'SDE: $1M'}]}}
        return {'web':{'results':[{'title':'Example Manufacturing','url':'https://example.com','description':'Manufacturing services'},{'title':'Example Manufacturing contact','url':'https://example.com/contact','description':'Company services'}]}}
    monkeypatch.setattr('app.jobs.BraveProvider.search',search)
    body={'criteria':Criteria().model_dump(),'budget':1,'idempotency_key':'sourcing-1'}
    a=client.post('/api/search',json=body);b=client.post('/api/search',json={**body,'idempotency_key':'sourcing-2'});assert a.json()['id']==b.json()['id']
    assert tick()
    job=client.get('/api/jobs').json()[0];assert job['status']=='incomplete' and job['progress']=={'brokered':1,'proprietary':1}
    assert client.get('/api/targets?category=brokered').json()[0]['screening']['status']=='Needs Verification'
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Evaluation))==0
        assert db.scalar(select(func.count()).select_from(Target))==2
        assert db.scalar(select(func.count()).select_from(Usage))==2
    csv=client.get('/api/export/brokered/csv');assert csv.status_code==200 and 'score' not in csv.text.lower()

def test_persistent_worker_recovers_expired_lease(user,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','fixture');monkeypatch.setattr('app.jobs.queries',lambda _:[])
    # Empty steps tested separately; expired evaluation-less sourcing state must become claimable.
    from app.jobs import claim
    with Session() as db:
        job=enqueue(db,user,'sourcing',{'criteria':Criteria().model_dump()},'recovery-key',1);job.status='running';job.cursor=4;job.lease=time.time()-10;db.commit();jid=job.id
    with Session() as db:
        claimed=claim(db);assert claimed.id==jid and claimed.cursor==4
    with Session() as db:assert claim(db) is None

def test_retries_preserve_collected_results(client,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','fixture')
    from app.discovery import TransientProviderError
    calls=[];steps=[{'category':'proprietary','query':'one','offset':0},{'category':'proprietary','query':'two','offset':0}]
    monkeypatch.setattr('app.jobs.queries',lambda _:steps)
    def search(self,query,offset):
        calls.append(query)
        if calls==['one','two']:raise TransientProviderError('Transient test response')
        return {'web':{'results':[{'title':'Example company','url':'https://'+query+'.example.com','description':'Company services'}]}}
    monkeypatch.setattr('app.jobs.BraveProvider.search',search)
    jid=client.post('/api/search',json={'criteria':Criteria(mode='proprietary').model_dump(),'budget':1,'idempotency_key':'retry-key'}).json()['id']
    assert tick()
    with Session() as db:
        j=db.get(Job,jid);assert j.status=='retrying' and j.cursor==1;j.lease=0;db.commit()
    assert tick();assert calls==['one','two','two']
    assert len(client.get('/api/targets?category=proprietary').json())==2

def test_budget_enforcement_no_unapproved_request(client,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','fixture')
    monkeypatch.setattr(config,'BRAVE_REQUEST_COST',.005)
    monkeypatch.setattr('app.jobs.BraveProvider.search',lambda *_:(_ for _ in ()).throw(AssertionError('Must not call provider')))
    jid=client.post('/api/search',json={'criteria':Criteria().model_dump(),'budget':.001,'idempotency_key':'budget-key'}).json()['id'];assert tick()
    j=client.get('/api/jobs').json()[0];assert j['id']==jid and j['status']=='failed' and 'spending limit' in j['error']

def test_cancel_before_request(client,monkeypatch):
    monkeypatch.setattr(config,'BRAVE_KEY','fixture')
    jid=client.post('/api/search',json={'criteria':Criteria().model_dump(),'budget':1,'idempotency_key':'cancel-key'}).json()['id']
    client.post(f'/api/jobs/{jid}/cancel');assert tick();assert client.get('/api/jobs').json()[0]['status']=='cancelled'

def test_only_selected_opportunity_evaluated_and_versions(client,monkeypatch):
    from tests.test_evaluation import analysis,CHUNKS
    from app.evaluation import finalize
    monkeypatch.setattr(config,'AI_KEY','fixture');first=standalone(client,'Selected');second=standalone(client,'Untouched')
    for oid in [first,second]:client.put(f'/api/opportunities/{oid}',json={'notes':'Revenue 1200000 and EBITDA 200000'})
    def fake_analyze(chunks,payload):
        assert payload['opportunity_id']==first
        return finalize(analysis(),FRAMEWORKS['proprietary'],CHUNKS,[]),{'prompt_tokens':100}
    monkeypatch.setattr('app.jobs.analyze',fake_analyze)
    r=client.post(f'/api/opportunities/{first}/evaluate',json={'budget':.25,'idempotency_key':'eval-key-1'});assert r.status_code==200
    assert client.put(f'/api/opportunities/{first}',json={'notes':'change midflight'}).status_code==409
    assert tick();assert len(client.get(f'/api/opportunities/{first}').json()['evaluations'])==1
    assert client.get(f'/api/opportunities/{second}').json()['evaluations']==[]
    client.put(f'/api/opportunities/{first}',json={'notes':'Updated reported financials'})
    client.post(f'/api/opportunities/{first}/evaluate',json={'budget':.25,'idempotency_key':'eval-key-2'});assert tick()
    versions=client.get(f'/api/opportunities/{first}').json()['evaluations'];assert len(versions)==2
    export=client.get('/api/evaluations/'+str(versions[0]['id'])+'/export');assert export.status_code==200 and 'Criterion-level' in export.text

def test_authorized_import_and_manual_fact_verification(client):
    cid=save_criteria(client)
    response=client.post('/api/import',data={'criteria_id':cid,'category':'proprietary'},files={'file':('export.csv',b'name,url,country,export_allowed\nExample,https://example.com,Canada,true\nExample duplicate,https://example.com/about,Canada,true')})
    assert response.status_code==200 and response.json()['progress']['proprietary']==1
    t=client.get('/api/targets?category=proprietary').json()[0];assert t['screening']['status']=='Needs Verification'
    r=client.post('/api/targets/'+str(t['id'])+'/facts',json={'key':'country','value':'Canada','source':'https://example.com','quote':'Company based in Canada.'})
    assert r.json()['screening']['status']=='Matches Known Criteria'

def test_settings_custom_presets_and_invalid_weights(client):
    r=client.put('/api/settings',json={'frameworks':{'brokered':{'valuation':100}}});assert r.status_code==400
    r=client.put('/api/settings',json={'monthly_budget':5,'search_budget':.5,'evaluation_budget':.1,'presets':{'strategy':{'category':'brokered','weights':FRAMEWORKS['brokered']}}});assert r.status_code==200
    assert client.get('/api/bootstrap').json()['settings']['presets']['strategy']['weights']['valuation']==20


def test_login_nonce_survives_favicon_and_parallel_login_page(user):
    import re
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        page=c.get('/login');nonce=re.search(r'name="nonce" value="([^"]+)"',page.text)[1]
        assert c.get('/favicon.ico').status_code==204
        c.get('/login')
        assert c.post('/login',data={'email':user.email,'password':'test-password-123','nonce':nonce}).status_code==200
