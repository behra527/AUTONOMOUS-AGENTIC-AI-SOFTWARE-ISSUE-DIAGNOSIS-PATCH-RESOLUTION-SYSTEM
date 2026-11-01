from unittest.mock import patch
import time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from app.config import settings
from app.db import Session, Snapshot, Repository, Chunk, Ticket, Job
from app.indexer import digest
from app.retrieval import search, similar_tickets
from app.worker import run_once
from conftest import headers


def test_signed_oidc_checks_issuer_audience_expiry(client, monkeypatch):
    monkeypatch.setattr(settings,'auth_mode','oidc')
    monkeypatch.setattr(settings,'oidc_issuer','https://identity.example')
    monkeypatch.setattr(settings,'oidc_audience','tracepoint')
    monkeypatch.setattr(settings,'oidc_jwks_url','https://identity.example/jwks')
    key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    claims = {'sub':'engineer','iss':'https://identity.example','aud':'tracepoint','iat':int(time.time()),'exp':int(time.time())+60}
    with patch('app.auth.jwks') as mock:
        mock.return_value.get_signing_key_from_jwt.return_value.key = key.public_key()
        good=jwt.encode(claims,key,algorithm='RS256')
        assert client.get('/api/v1/projects',headers={'Authorization':'Bearer '+good}).status_code == 200
        for changed in [{'aud':'wrong'},{'iss':'https://evil.example'},{'exp':int(time.time())-60}]:
            bad=jwt.encode({**claims,**changed},key,algorithm='RS256')
            assert client.get('/api/v1/projects',headers={'Authorization':'Bearer '+bad}).status_code == 401
        bad=jwt.encode(claims,'a-long-test-secret-not-for-production',algorithm='HS256')
        assert client.get('/api/v1/projects',headers={'Authorization':'Bearer '+bad}).status_code == 401


def test_semantic_retrieval_is_snapshot_scoped(monkeypatch):
    monkeypatch.setattr(settings,'embedding_model','test-embedding')
    with Session() as db:
        repo=Repository(id='repo',project_id='p1',name='repo',remote_url='https://github.com/example/repo')
        db.add(repo); db.flush()
        db.add_all([Snapshot(id=s,repository_id='repo',commit_sha=sha*40,status='READY',stats={'embedding_model':'test-embedding'}) for s,sha in [('s1','a'),('s2','b')]])
        db.flush()
        for id,snapshot,content in [('one','s1','upload file'),('two','s2','private tenant source')]:
            db.add(Chunk(id=id,snapshot_id=snapshot,path='app.py',symbol='upload',kind='function',start_line=1,end_line=1,content=content,content_hash=digest(content),embedding=[1.0]+[0.0]*1535))
        db.commit()
        with patch('app.retrieval.embeddings',return_value=[[1.0]+[0.0]*1535]):
            result=search(db,'s1','document attachment')
            assert [c.id for c,_ in result] == ['one']


def test_history_stays_in_project():
    fields={'title':'PDF upload failure','description':'PDF upload failure at size limit','expected_behavior':'Accept','actual_behavior':'Failure','reproduction_steps':['Upload'],'customer_id':'customer'}
    with Session() as db:
        db.add_all([Ticket(id='current',project_id='p1',**fields),Ticket(id='same',project_id='p1',**fields),Ticket(id='other',project_id='p2',**fields)])
        db.commit()
        assert [h['ticket_id'] for h in similar_tickets(db,db.get(Ticket,'current'))] == ['same']


def test_exhausted_job_becomes_failed():
    with Session() as db:
        db.add(Repository(id='repo',project_id='p1',name='repo',remote_url='example'))
        db.flush()
        db.add(Snapshot(id='snap',repository_id='repo',commit_sha='a'*40,status='INDEXING'))
        db.flush()
        db.add(Job(id='job',project_id='p1',kind='INDEX',target_id='snap',status='RUNNING',attempts=3,lease_until=1))
        db.commit()
    run_once()
    with Session() as db:
        assert db.get(Job,'job').status == 'FAILED'
        assert db.get(Snapshot,'snap').status == 'FAILED'
