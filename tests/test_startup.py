import os
from pathlib import Path
import shutil
import subprocess
import time
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app import config
from app.db import Session,User
from app.main import app


def cli_env(tmp_path):
    env=os.environ.copy();env['DATA_DIR']=str(tmp_path);env['DATABASE_URL']='sqlite:///'+str(tmp_path/'setup.db');env['ADMIN_EMAIL']='setup@example.com';env['ADMIN_PASSWORD']='test-setup-password-123'
    return env


def test_cli_setup_creates_first_user_once(tmp_path):
    env=cli_env(tmp_path)
    result=subprocess.run([str(config.ROOT/'.venv/bin/python'),'-m','app.cli','setup'],env=env,cwd=config.ROOT,text=True,capture_output=True)
    assert result.returncode==0 and 'Account created' in result.stdout
    # No credentials needed on a repeat setup; do not change the existing password.
    env.pop('ADMIN_PASSWORD');env.pop('ADMIN_EMAIL')
    result=subprocess.run([str(config.ROOT/'.venv/bin/python'),'-m','app.cli','setup'],env=env,cwd=config.ROOT,text=True,capture_output=True)
    assert result.returncode==0 and 'account already exists' in result.stdout


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


def test_process_helper_is_portable_and_rejects_unrelated_pid():
    helper=config.ROOT/'scripts/process-helpers.sh'
    result=subprocess.run(['bash','-c',f'source "{helper}"; process_matches $$ impossible-command "{config.ROOT}"'],capture_output=True)
    assert result.returncode!=0
    for name in ['dev-start.sh','dev-stop.sh','process-helpers.sh']:
        text=(config.ROOT/'scripts'/name).read_text()
        assert 'readlink ' not in text and '| rg ' not in text and '/proc/' not in text.replace('# Shared POSIX process checks for Linux and macOS; no /proc or ripgrep dependency.','')


def test_health_and_bootstrap_expose_matching_api_contract(client,monkeypatch):
    monkeypatch.setenv('APP_INSTANCE_ID','test-startup-instance')
    health=client.get('/health').json()
    assert health['api_version']==2 and health['instance_id']=='test-startup-instance'
    assert client.get('/api/bootstrap').json()['api_version']==health['api_version']


def test_start_script_does_not_claim_success_for_an_old_listener(tmp_path):
    import http.server
    import socketserver
    import threading
    class OldHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b'{"status":"ok","database":"connected"}')
        def log_message(self,*args):pass
    with socketserver.TCPServer(('127.0.0.1',0),OldHandler) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        port=server.server_address[1]
        env=cli_env(tmp_path);env['DEV_PORT']=str(port)
        result=subprocess.run(['bash',str(config.ROOT/'scripts/dev-start.sh')],cwd=config.ROOT,env=env,capture_output=True,text=True,timeout=15)
        assert result.returncode!=0
        assert 'already in use' in result.stdout and 'no new server was started' in result.stdout
        assert 'Development service started.' not in result.stdout
        assert not list(tmp_path.glob('web*.pid'))
        server.shutdown()


def test_health_handshake_rejects_another_instance(tmp_path):
    import http.server
    import socketserver
    import threading
    class OtherHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b'{"status":"ok","api_version":2,"instance_id":"other-instance"}')
        def log_message(self,*args):pass
    with socketserver.TCPServer(('127.0.0.1',0),OtherHandler) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        command=f'project_root="{config.ROOT}"; source "{config.ROOT}/scripts/process-helpers.sh"; server_matches {server.server_address[1]} expected-instance'
        assert subprocess.run(['bash','-c',command],capture_output=True).returncode!=0
        server.shutdown()
