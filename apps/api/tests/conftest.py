import os
import tempfile
from pathlib import Path

_temp = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_temp.name) / 'tests.db').replace('\\', '/')
os.environ['DATA_DIR'] = str(Path(_temp.name) / 'data')
os.environ['AUTH_MODE'] = 'demo'
os.environ['MODEL_MODE'] = 'demo'
os.environ['EMBEDDING_MODEL'] = ''

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, Session, Project, Membership
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session() as db:
        db.add_all([Project(id='p1', tenant_id='t1', name='One'), Project(id='p2', tenant_id='t2', name='Two')])
        db.flush()
        db.add_all([Membership(subject=s, project_id=p, role=r) for s, p, r in [
            ('customer', 'p1', 'customer'), ('engineer', 'p1', 'engineer'), ('admin', 'p1', 'admin'), ('other', 'p2', 'customer')]])
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()


def headers(role='engineer', key='test-key'):
    return {'Authorization': f'Bearer demo-{role}', 'Idempotency-Key': key}
