import os
from pathlib import Path
import shutil
import subprocess
import time
from fastapi.testclient import TestClient
from app import config
from app.main import app


def test_dotenv_loads_without_overriding_injected_values(tmp_path):
    (tmp_path/'app').mkdir();shutil.copy(config.ROOT/'app/config.py',tmp_path/'app/config.py')
    (tmp_path/'.env').write_text('APOLLO_API_KEY=dotenv-fixture\nAPOLLO_CREDIT_COST_USD=0.025\n')
    env=os.environ.copy();env['APOLLO_API_KEY']='injected-fixture';env.pop('APOLLO_CREDIT_COST_USD',None)
    script=f"import runpy; c=runpy.run_path({str(tmp_path/'app/config.py')!r}); assert c['APOLLO_KEY']=='injected-fixture'; assert c['APOLLO_CREDIT_COST']==0.025; print('dotenv precedence checked')"
    result=subprocess.run([str(config.ROOT/'.venv/bin/python'),'-c',script],env=env,capture_output=True,text=True)
    assert result.returncode==0


def test_embedded_worker_processes_job_without_second_process(client,monkeypatch):
    monkeypatch.setattr(config,'EMBEDDED_WORKER',True);monkeypatch.setattr(config,'BRAVE_KEY','fixture')
    monkeypatch.setattr('app.jobs.queries',lambda _: [{'category':'proprietary','query':'company','offset':0}])
    monkeypatch.setattr('app.jobs.BraveProvider.search',lambda *args,**kwargs:{'web':{'results':[{'title':'Embedded worker fixture','url':'https://embedded.example.com','description':'Company services'}]}})
    with TestClient(app) as running:
        assert running.get('/health').json()['embedded_worker_alive']
        response=client.post('/api/search',json={'criteria':{'mode':'proprietary'},'budget':1,'idempotency_key':'embedded-worker-check'})
        assert response.status_code==200
        deadline=time.time()+5
        while time.time()<deadline:
            job=client.get('/api/jobs').json()[0]
            if job['status'] not in ['queued','running','retrying']:break
            time.sleep(.05)
        assert job['status']=='incomplete'
        assert len(client.get('/api/targets?category=proprietary').json())==1


def test_health_and_bootstrap_expose_matching_api_contract(client,monkeypatch):
    health=client.get('/health').json()
    assert health['api_version']==2
    assert client.get('/api/bootstrap').json()['api_version']==health['api_version']

