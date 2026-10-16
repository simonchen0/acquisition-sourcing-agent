import os
import tempfile
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='acquisition-tests-')
from sqlalchemy.engine import make_url
test_url=os.environ.get('TEST_DATABASE_URL')
if test_url and not (make_url(test_url).database or '').endswith(('_test','_tests')):
    raise RuntimeError('TEST_DATABASE_URL must name a dedicated database ending in _test or _tests. Tests recreate its tables.')
os.environ['DATABASE_URL']=test_url or 'sqlite:///'+os.environ['DATA_DIR']+'/tests.db'
# Never let the developer's root .env leak real keys or a live worker into tests.
for key in ['BRAVE_SEARCH_API_KEY','AI_API_KEY','OPENAI_API_KEY','APOLLO_API_KEY','DOCUMENT_ENCRYPTION_KEY']: os.environ[key]=''
os.environ['EMBEDDED_WORKER']='false'
os.environ['BRAVE_EXPORT_RIGHTS_CONFIRMED']='false'
os.environ['APOLLO_CREDIT_COST_USD']='0'
os.environ['APOLLO_STORAGE_RIGHTS_CONFIRMED']='false'
os.environ['APOLLO_EXPORT_RIGHTS_CONFIRMED']='false'
os.environ['BRAVE_STORAGE_RIGHTS_CONFIRMED']='true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base,engine,Session,local_user

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield

@pytest.fixture
def user():
    with Session() as db: return local_user(db)

@pytest.fixture
def client(user):
    import re
    with TestClient(app) as client:
        page=client.get('/'); csrf=re.search(r'name="csrf-token" content="([^"]+)"',page.text)[1]
        client.headers['X-CSRF-Token']=csrf
        yield client
