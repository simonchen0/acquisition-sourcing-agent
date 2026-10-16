import os
import tempfile
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='acquisition-tests-')
from sqlalchemy.engine import make_url
test_url=os.environ.get('TEST_DATABASE_URL')
if test_url and not (make_url(test_url).database or '').endswith(('_test','_tests')):
    raise RuntimeError('TEST_DATABASE_URL must name a dedicated database ending in _test or _tests. Tests recreate its tables.')
os.environ['DATABASE_URL']=test_url or 'sqlite:///'+os.environ['DATA_DIR']+'/tests.db'
os.environ['COOKIE_SECURE']='false'
os.environ['EMBEDDED_WORKER']='false'
for credential in ['APOLLO_API_KEY','BRAVE_SEARCH_API_KEY','AI_API_KEY','OPENAI_API_KEY']:
    os.environ[credential]=''  # Tests must never inherit paid credentials from .env or the host.
os.environ['APOLLO_CREDIT_COST_USD']='0'
os.environ['BRAVE_STORAGE_RIGHTS_CONFIRMED']='true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base,engine,Session,User
from app.security import hash_password

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield

@pytest.fixture
def user():
    with Session() as db:
        u=User(email='searcher@example.com',password=hash_password('test-password-123')); db.add(u); db.commit(); return u

@pytest.fixture
def client(user):
    import re
    with TestClient(app) as client:
        r=client.get('/login'); nonce=re.search(r'name="nonce" value="([^"]+)"',r.text)[1]
        assert client.post('/login',data={'email':user.email,'password':'test-password-123','nonce':nonce}).status_code==200
        page=client.get('/'); csrf=re.search(r'name="csrf-token" content="([^"]+)"',page.text)[1]
        client.headers['X-CSRF-Token']=csrf
        yield client
