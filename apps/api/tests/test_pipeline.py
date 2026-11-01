import json
from pathlib import Path
import time
from unittest.mock import patch
import pytest
from sqlalchemy import select
from app.db import Session, Chunk, Investigation, Job, Ticket, Membership
from app.config import settings
from app.indexer import extract, git, validate_remote, digest
from app.retrieval import search
from app.worker import run_once
from app.investigator import investigate
from conftest import headers

BODY = {'title': 'PDF upload fails at size limit', 'description': 'Uploading a five megabyte PDF raises a ValueError.',
        'expected_behavior': 'Accept PDF at the five MiB limit', 'actual_behavior': 'Server error',
        'reproduction_steps': ['Select PDF', 'Upload file']}


def fixture_repo(tmp_path, monkeypatch):
    root = tmp_path / 'repos'
    root.mkdir()
    repo = root / 'service'
    repo.mkdir()
    (repo / 'upload.py').write_text('MAX_PDF_BYTES = 5 * 1024 * 1024\n\ndef validate_pdf_upload(content):\n    if len(content) >= MAX_PDF_BYTES:\n        raise ValueError("PDF upload exceeds size limit")\n    return len(content)\n')
    (repo / 'README.md').write_text('PDF uploads up to and including five MiB must be accepted.')
    (repo / '.env').write_text('API_KEY=do-not-index-this')
    (repo / 'unsafe.py').write_text('password = "do-not-index-this"')
    git('init', repo)
    git('-C', repo, 'add', '.')
    git('-C', repo, '-c', 'user.name=Tests', '-c', 'user.email=tests@localhost', 'commit', '-m', 'fixture')
    sha = git('-C', repo, 'rev-parse', 'HEAD').decode().strip()
    monkeypatch.setattr(settings, 'local_repo_root', root)
    return repo, sha


def indexed(client, tmp_path, monkeypatch):
    repo, sha = fixture_repo(tmp_path, monkeypatch)
    response = client.post('/api/v1/repositories', headers=headers('admin'), json={'project_id': 'p1', 'name': 'Service', 'remote_url': str(repo)})
    assert response.status_code == 201, response.text
    repo_id = response.json()['id']
    response = client.post(f'/api/v1/repositories/{repo_id}/index', headers=headers(), json={'commit_sha': sha})
    assert response.status_code == 202, response.text
    snap = response.json()['snapshot_id']
    assert run_once()
    with Session() as db:
        assert db.scalar(select(Job)).status == 'COMPLETED'
    return repo_id, sha, snap


def test_full_pipeline_and_customer_privacy(client, tmp_path, monkeypatch):
    repo_id, sha, snapshot = indexed(client, tmp_path, monkeypatch)
    response = client.post('/api/v1/projects/p1/tickets', headers=headers('customer'), json=BODY)
    assert response.status_code == 201
    ticket = response.json()['id']
    response = client.post(f'/api/v1/tickets/{ticket}/investigations', headers=headers(), json={'repository_id': repo_id, 'commit_sha': sha})
    assert response.status_code == 202
    run_id = response.json()['run_id']
    assert run_once()
    diagnosis = client.get(f'/api/v1/investigations/{run_id}', headers=headers()).json()
    assert diagnosis['status'] == 'COMPLETED'
    assert diagnosis['diagnosis']['verified'] is False
    evidence = client.get(f'/api/v1/investigations/{run_id}/evidence', headers=headers()).json()
    assert any(e['symbol'] == 'validate_pdf_upload' for e in evidence)
    assert all(e['commit_sha'] == sha and e['hash_valid'] for e in evidence)
    assert not any(e['path'] in ('.env', 'unsafe.py') for e in evidence)
    safe = client.get(f'/api/v1/investigations/{run_id}', headers=headers('customer')).json()
    assert 'diagnosis' not in safe and 'snapshot_id' not in safe
    assert client.get(f'/api/v1/investigations/{run_id}/evidence', headers=headers('customer')).status_code == 403
    assert client.get(f'/api/v1/tickets/{ticket}', headers=headers('other')).status_code == 404
    assert client.get(f'/api/v1/snapshots/{snapshot}/search?q=PDF', headers=headers('other')).status_code == 404
    assert client.get(f'/api/v1/investigations/{run_id}', headers=headers('other')).status_code == 404
    assert client.get('/api/v1/projects/p1/jobs', headers=headers('customer')).status_code == 403


def test_idempotency_and_validation(client):
    url = '/api/v1/projects/p1/tickets'
    first = client.post(url, headers=headers('customer'), json=BODY)
    again = client.post(url, headers=headers('customer'), json=BODY)
    assert first.json()['id'] == again.json()['id']
    assert client.post(url, headers=headers('customer'), json={**BODY, 'title': 'Different issue'}).status_code == 409
    assert client.post(url, headers=headers('customer','another'), json={**BODY, 'reproduction_steps': ['']}).status_code == 422
    assert client.get('/api/v1/projects').status_code == 401
    assert client.get('/api/v1/projects', headers=headers('other')).json() == [{'id':'p2','name':'Two'}]
    assert client.post(url, headers=headers('other'), json=BODY).status_code == 404


def test_ast_nested_async_and_exact_hash():
    text = 'import os\nclass Service:\n    async def upload(self):\n        return len([])\n'
    chunks = extract('service.py', text)
    method = next(c for c in chunks if c['symbol'] == 'Service.upload')
    assert method['start_line'] == 3 and method['end_line'] == 4
    assert method['metadata_']['call_candidates'] == ['len']
    assert method['content_hash'] == digest('\n'.join(text.splitlines()[2:4]))


@pytest.mark.parametrize('url', ['http://github.com/a/b', 'https://localhost/a', 'https://github.com:8443/a', 'https://token@github.com/a', 'https://github.com/a?token=secret', 'ext::command'])
def test_unsafe_remote_rejected(url):
    with pytest.raises(ValueError):
        validate_remote(url)


def test_failed_worker_escalates(client, tmp_path, monkeypatch):
    repo, sha, _ = indexed(client, tmp_path, monkeypatch)
    ticket = client.post('/api/v1/projects/p1/tickets', headers=headers('customer'), json=BODY).json()['id']
    run = client.post(f'/api/v1/tickets/{ticket}/investigations', headers=headers(), json={'repository_id':repo,'commit_sha':sha}).json()['run_id']
    with patch('app.worker.investigate', side_effect=RuntimeError('secret provider error')):
        assert run_once()
    assert client.get(f'/api/v1/tickets/{ticket}', headers=headers('customer')).json()['status'] == 'ESCALATED'
    assert client.get(f'/api/v1/investigations/{run}', headers=headers()).json()['status'] == 'FAILED'
    jobs = client.get('/api/v1/projects/p1/jobs', headers=headers()).text
    assert 'secret provider error' not in jobs


def test_model_rejects_fake_evidence(monkeypatch):
    monkeypatch.setattr(settings, 'model_mode', 'live')
    monkeypatch.setattr(settings, 'model_base_url', 'https://model.invalid/v1')
    monkeypatch.setattr(settings, 'model_api_key', 'test')
    monkeypatch.setattr(settings, 'model_name', 'test')
    fake = {'summary':'Maybe','hypotheses':[{'title':'Fake','explanation':'Unsupported','evidence_ids':['invented']}], 'missing_information':[], 'limitations':[]}
    with patch('app.investigator.httpx.Client') as mock:
        mock.return_value.__enter__.return_value.post.return_value.json.return_value = {'choices':[{'message':{'content':json.dumps(fake)}}]}
        with pytest.raises(ValueError, match='unknown evidence'):
            investigate(Ticket(**BODY), [])


def test_tampered_evidence_is_rejected():
    with pytest.raises(ValueError, match='integrity'):
        investigate(Ticket(**BODY), [Chunk(content='tampered', content_hash=digest('original'))])


def test_lease_reclaims_interrupted_job(client, tmp_path, monkeypatch):
    repo, sha = fixture_repo(tmp_path, monkeypatch)
    repo_id = client.post('/api/v1/repositories',headers=headers('admin'),json={'project_id':'p1','name':'Service','remote_url':str(repo)}).json()['id']
    client.post(f'/api/v1/repositories/{repo_id}/index',headers=headers(),json={'commit_sha':sha})
    with Session() as db:
        job = db.scalar(select(Job)); job.status='RUNNING'; job.attempts=1; job.lease_until=time.time()-10; db.commit()
    assert run_once()
    with Session() as db:
        job = db.scalar(select(Job)); assert job.status=='COMPLETED' and job.attempts==2


def test_oidc_fail_closed(client, monkeypatch):
    monkeypatch.setattr(settings, 'auth_mode', 'oidc')
    assert client.get('/api/v1/projects',headers=headers('admin')).status_code == 503


def test_same_tenant_other_customer_cannot_read(client):
    ticket = client.post('/api/v1/projects/p1/tickets',headers=headers('customer'),json=BODY).json()['id']
    with Session() as db:
        db.add(Membership(subject='other',project_id='p1',role='customer'));db.commit()
    assert client.get(f'/api/v1/tickets/{ticket}',headers=headers('other')).status_code == 404
    assert client.get('/api/v1/projects/p1/tickets',headers=headers('other')).json()['items'] == []
