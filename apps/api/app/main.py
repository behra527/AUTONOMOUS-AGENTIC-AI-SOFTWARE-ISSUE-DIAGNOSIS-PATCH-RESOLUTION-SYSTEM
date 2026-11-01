import hashlib
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import (get_db, Project, Membership, Ticket, Repository, Snapshot, Chunk, Investigation,
                 Job, AuditEvent, Idempotency, Attachment)
from .auth import principal, authorize
from .schemas import TicketInput, RepoInput, IndexInput, InvestigationInput, AttachmentInput
from .redaction import sanitize_log
from .indexer import validate_remote, digest
from .retrieval import search

app = FastAPI(title='BugHound-Ai | Issue Investigation', version='0.2.0')
PREFIX = '/api/v1'


@app.middleware('http')
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


def error(request, status, code, message):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message,
                                                             'request_id': request.state.request_id}})


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error(request, exc.status_code, f'HTTP_{exc.status_code}', str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error(request, 422, 'INVALID_INPUT', '; '.join(f'{".".join(map(str, e["loc"]))}: {e["msg"]}' for e in exc.errors()))


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return error(request, 409, 'CONFLICT', 'Concurrent or duplicate request. Refresh and retry with the same idempotency key.')


def must_get(db, model, id):
    item = db.get(model, id)
    if not item:
        raise HTTPException(404, 'Resource not found')
    return item


def ticket_access(db, subject, id, internal=False):
    ticket = must_get(db, Ticket, id)
    membership = authorize(db, subject, ticket.project_id, internal=internal)
    if membership.role == 'customer' and ticket.customer_id != subject:
        raise HTTPException(404, 'Resource not found')
    return ticket, membership


def dump(item, fields):
    return {f: getattr(item, f) for f in fields.split()}


TICKET_FIELDS = 'id project_id title description expected_behavior actual_behavior reproduction_steps status created_at'


def deduplicate(db, subject, route, key, body):
    if not key or len(key) > 100:
        raise HTTPException(400, 'Idempotency-Key of 1-100 characters is required')
    scoped = f'{subject}:{route}:{key}'
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    existing = db.get(Idempotency, scoped)
    if existing and existing.request_hash != fingerprint:
        raise HTTPException(409, 'Idempotency key already used for different input')
    return scoped, fingerprint, existing.response if existing else None


def record(db, project, subject, action, target):
    db.add(AuditEvent(project_id=project, actor=subject, action=action, target_id=target))


@app.get(PREFIX + '/health')
def health():
    return {'status': 'ok', 'auth_mode': settings.auth_mode, 'model_mode': settings.model_mode,
            'oidc': {'authority': settings.oidc_issuer, 'client_id': settings.oidc_client_id,
                     'redirect_uri': settings.oidc_redirect_uri, 'scope': settings.oidc_scope},
            'semantic_enabled': bool(settings.embedding_model), 'milestone': 'Phase 1 + 2 implementation; acceptance pending live integrations'}


@app.get(PREFIX + '/auth/me')
def me(subject=Depends(principal), db=Depends(get_db)):
    members = db.scalars(select(Membership).where(Membership.subject == subject))
    return {'subject': subject, 'auth_mode': settings.auth_mode,
            'memberships': [dump(m, 'project_id role') for m in members]}


@app.get(PREFIX + '/projects')
def projects(subject=Depends(principal), db=Depends(get_db)):
    rows = db.scalars(select(Project).join(Membership).where(Membership.subject == subject))
    return [dump(p, 'id name') for p in rows]


@app.get(PREFIX + '/projects/{project_id}/tickets')
def tickets(project_id: str, before: str | None = None, limit: int = Query(50, ge=1, le=100), subject=Depends(principal), db=Depends(get_db)):
    member = authorize(db, subject, project_id)
    stmt = select(Ticket).where(Ticket.project_id == project_id)
    if member.role == 'customer':
        stmt = stmt.where(Ticket.customer_id == subject)
    if before:
        stmt = stmt.where(Ticket.id < before)
    rows = list(db.scalars(stmt.order_by(Ticket.id.desc()).limit(limit + 1)))
    return {'items': [dump(t, TICKET_FIELDS) for t in rows[:limit]], 'next_cursor': rows[limit-1].id if len(rows) > limit else None}


@app.post(PREFIX + '/projects/{project_id}/tickets', status_code=201)
def create_ticket(project_id: str, body: TicketInput, idempotency_key: str = Header(default=''), subject=Depends(principal), db=Depends(get_db)):
    authorize(db, subject, project_id)
    if any(len(s) > 1000 or not s.strip() for s in body.reproduction_steps):
        raise HTTPException(422, 'Each reproduction step must contain 1-1000 characters')
    key, fingerprint, cached = deduplicate(db, subject, project_id + '/tickets', idempotency_key, body.model_dump())
    if cached:
        return cached
    ticket = Ticket(project_id=project_id, customer_id=subject, **body.model_dump())
    db.add(ticket)
    db.flush()
    response = dump(ticket, TICKET_FIELDS)
    db.add(Idempotency(key=key, request_hash=fingerprint, response=response))
    record(db, project_id, subject, 'TICKET_CREATED', ticket.id)
    db.commit()
    return response


@app.get(PREFIX + '/tickets/{ticket_id}')
def get_ticket(ticket_id: str, subject=Depends(principal), db=Depends(get_db)):
    ticket, _ = ticket_access(db, subject, ticket_id)
    return dump(ticket, TICKET_FIELDS)


@app.post(PREFIX + '/tickets/{ticket_id}/attachments', status_code=201)
def add_attachment(ticket_id: str, body: AttachmentInput, subject=Depends(principal), db=Depends(get_db)):
    ticket, _ = ticket_access(db, subject, ticket_id)
    # Serialize per-ticket uploads on both database backends before enforcing quota.
    db.execute(update(Ticket).where(Ticket.id == ticket_id).values(status=Ticket.status))
    if db.scalar(select(func.count()).select_from(Attachment).where(Attachment.ticket_id == ticket_id)) >= 5:
        raise HTTPException(409, 'At most five text logs are allowed per issue')
    try:
        content, redacted = sanitize_log(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    attachment = Attachment(ticket_id=ticket_id, filename=body.filename, content=content, content_hash=digest(content), redacted=redacted)
    db.add(attachment)
    db.flush()
    record(db, ticket.project_id, subject, 'ATTACHMENT_ADDED', attachment.id)
    db.commit()
    return dump(attachment, 'id filename content_hash redacted created_at')


@app.get(PREFIX + '/tickets/{ticket_id}/attachments')
def attachments(ticket_id: str, subject=Depends(principal), db=Depends(get_db)):
    ticket_access(db, subject, ticket_id)
    return [dump(a, 'id filename content content_hash redacted created_at') for a in db.scalars(select(Attachment).where(Attachment.ticket_id == ticket_id).order_by(Attachment.created_at))]


@app.get(PREFIX + '/projects/{project_id}/repositories')
def repositories(project_id: str, subject=Depends(principal), db=Depends(get_db)):
    authorize(db, subject, project_id, internal=True)
    result = []
    for repo in db.scalars(select(Repository).where(Repository.project_id == project_id)):
        result.append({**dump(repo, 'id name remote_url project_id'), 'snapshots': [dump(s, 'id commit_sha status stats') for s in db.scalars(select(Snapshot).where(Snapshot.repository_id == repo.id))]})
    return result


@app.post(PREFIX + '/repositories', status_code=201)
def register_repo(body: RepoInput, subject=Depends(principal), db=Depends(get_db)):
    authorize(db, subject, body.project_id, admin=True)
    try:
        validate_remote(body.remote_url)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    repo = Repository(**body.model_dump())
    db.add(repo)
    db.flush()
    record(db, repo.project_id, subject, 'REPOSITORY_REGISTERED', repo.id)
    db.commit()
    return dump(repo, 'id name remote_url project_id')


@app.post(PREFIX + '/repositories/{repo_id}/index', status_code=202)
def index(repo_id: str, body: IndexInput, subject=Depends(principal), db=Depends(get_db)):
    repo = must_get(db, Repository, repo_id)
    authorize(db, subject, repo.project_id, internal=True)
    snapshot = db.scalar(select(Snapshot).where(Snapshot.repository_id == repo_id, Snapshot.commit_sha == body.commit_sha))
    if snapshot and snapshot.status != 'FAILED':
        job = db.scalar(select(Job).where(Job.target_id == snapshot.id).order_by(Job.created_at.desc()))
        return {'snapshot_id': snapshot.id, 'job_id': job.id if job else None, 'status': snapshot.status}
    if not snapshot:
        snapshot = Snapshot(repository_id=repo_id, commit_sha=body.commit_sha)
        db.add(snapshot)
        db.flush()
    snapshot.status = 'QUEUED'
    job = Job(project_id=repo.project_id, kind='INDEX', target_id=snapshot.id)
    db.add(job)
    db.flush()
    record(db, repo.project_id, subject, 'INDEX_QUEUED', snapshot.id)
    db.commit()
    return {'snapshot_id': snapshot.id, 'job_id': job.id, 'status': 'QUEUED'}


@app.post(PREFIX + '/tickets/{ticket_id}/investigations', status_code=202)
def start_investigation(ticket_id: str, body: InvestigationInput, idempotency_key: str = Header(default=''), subject=Depends(principal), db=Depends(get_db)):
    ticket, _ = ticket_access(db, subject, ticket_id, internal=True)
    repo = must_get(db, Repository, body.repository_id)
    if repo.project_id != ticket.project_id:
        raise HTTPException(404, 'Resource not found')
    key, fingerprint, cached = deduplicate(db, subject, ticket_id + '/investigations', idempotency_key, body.model_dump())
    if cached:
        return cached
    snapshot = db.scalar(select(Snapshot).where(Snapshot.repository_id == repo.id, Snapshot.commit_sha == body.commit_sha, Snapshot.status == 'READY'))
    if not snapshot:
        raise HTTPException(409, 'Index this exact commit successfully before investigation')
    claimed = db.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.status.not_in(['QUEUED', 'INVESTIGATING'])).values(status='QUEUED'))
    if claimed.rowcount != 1:
        raise HTTPException(409, 'An investigation is already running')
    run = Investigation(ticket_id=ticket.id, snapshot_id=snapshot.id)
    db.add(run)
    db.flush()
    job = Job(project_id=ticket.project_id, kind='INVESTIGATE', target_id=run.id)
    db.add(job)
    db.flush()
    ticket.status = 'QUEUED'
    response = {'run_id': run.id, 'job_id': job.id, 'status_url': f'{PREFIX}/investigations/{run.id}'}
    db.add(Idempotency(key=key, request_hash=fingerprint, response=response))
    record(db, ticket.project_id, subject, 'INVESTIGATION_QUEUED', run.id)
    db.commit()
    return response


def project_run(db, subject, run):
    _, membership = ticket_access(db, subject, run.ticket_id)
    if membership.role == 'customer':
        return dump(run, 'id ticket_id status created_at')
    return dump(run, 'id ticket_id snapshot_id status diagnosis created_at')


@app.get(PREFIX + '/tickets/{ticket_id}/investigations')
def runs(ticket_id: str, subject=Depends(principal), db=Depends(get_db)):
    ticket_access(db, subject, ticket_id)
    return [project_run(db, subject, r) for r in db.scalars(select(Investigation).where(Investigation.ticket_id == ticket_id).order_by(Investigation.created_at.desc()))]


@app.get(PREFIX + '/investigations/{run_id}')
def get_run(run_id: str, subject=Depends(principal), db=Depends(get_db)):
    return project_run(db, subject, must_get(db, Investigation, run_id))


def evidence_row(chunk, snapshot):
    if digest(chunk.content) != chunk.content_hash:
        raise HTTPException(409, 'Evidence integrity mismatch')
    return {**dump(chunk, 'id path symbol kind start_line end_line content content_hash'),
            'metadata': chunk.metadata_, 'commit_sha': snapshot.commit_sha, 'snapshot_id': snapshot.id, 'hash_valid': True}


@app.get(PREFIX + '/investigations/{run_id}/evidence')
def evidence(run_id: str, subject=Depends(principal), db=Depends(get_db)):
    run = must_get(db, Investigation, run_id)
    ticket_access(db, subject, run.ticket_id, internal=True)
    snapshot = db.get(Snapshot, run.snapshot_id)
    chunks = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(run.evidence_ids), Chunk.snapshot_id == run.snapshot_id))}
    if len(chunks) != len(run.evidence_ids):
        raise HTTPException(409, 'Investigation evidence is incomplete')
    return [evidence_row(chunks[id], snapshot) for id in run.evidence_ids]


@app.get(PREFIX + '/snapshots/{snapshot_id}/search')
def search_snapshot(snapshot_id: str, q: str = Query(min_length=2, max_length=1000), subject=Depends(principal), db=Depends(get_db)):
    snapshot = must_get(db, Snapshot, snapshot_id)
    repo = db.get(Repository, snapshot.repository_id)
    authorize(db, subject, repo.project_id, internal=True)
    if snapshot.status != 'READY':
        raise HTTPException(409, 'Snapshot is not ready')
    return [{**evidence_row(c, snapshot), 'score': score} for c, score in search(db, snapshot_id, q)]


@app.get(PREFIX + '/projects/{project_id}/jobs')
def jobs(project_id: str, subject=Depends(principal), db=Depends(get_db)):
    authorize(db, subject, project_id, internal=True)
    return [dump(j, 'id kind target_id status attempts error created_at') for j in db.scalars(select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(50))]


@app.get(PREFIX + '/projects/{project_id}/audit-events')
def audit(project_id: str, subject=Depends(principal), db=Depends(get_db)):
    authorize(db, subject, project_id, internal=True)
    return [dump(e, 'id actor action target_id created_at') for e in db.scalars(select(AuditEvent).where(AuditEvent.project_id == project_id).order_by(AuditEvent.created_at.desc()).limit(100))]


web_dist = Path('apps/web/dist')
if web_dist.exists():
    app.mount('/', StaticFiles(directory=web_dist, html=True), name='portal')
