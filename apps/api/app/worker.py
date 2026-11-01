import logging
import time
from sqlalchemy import select, update, delete, or_, and_
from .db import Session, Job, Snapshot, Repository, Chunk, Investigation, Ticket, AuditEvent, Attachment
from .indexer import source_objects, extract
from .retrieval import embeddings, search
from .investigator import investigate
from .config import settings

log = logging.getLogger(__name__)


def run_once():
    with Session() as db:
        exhausted = list(db.scalars(select(Job).where(Job.status == 'RUNNING', Job.lease_until < time.time(), Job.attempts >= 3)))
        for old in exhausted:
            old.status = 'FAILED'
            old.error = 'Worker recovery limit reached; engineer intervention required.'
            if old.kind == 'INDEX':
                db.get(Snapshot, old.target_id).status = 'FAILED'
            elif old.kind == 'INVESTIGATE':
                run = db.get(Investigation, old.target_id)
                run.status = 'FAILED'
                db.get(Ticket, run.ticket_id).status = 'ESCALATED'
            db.add(AuditEvent(project_id=old.project_id, actor='worker', action='RECOVERY_EXHAUSTED', target_id=old.target_id))
        db.commit()
        eligible = or_(Job.status == 'QUEUED', and_(Job.status == 'RUNNING', Job.lease_until < time.time()))
        job = db.scalar(select(Job).where(eligible, Job.attempts < 3).order_by(Job.created_at).limit(1))
        if not job:
            return False
        # Compare-and-swap works on both PostgreSQL and the single-machine SQLite demo.
        claimed = db.execute(update(Job).where(Job.id == job.id, eligible, Job.attempts == job.attempts)
                             .values(status='RUNNING', attempts=Job.attempts + 1, lease_until=time.time() + 3600))
        db.commit()
        if claimed.rowcount != 1:
            return True
        db.refresh(job)
        attempt = job.attempts
        try:
            if job.kind == 'INDEX':
                snapshot = db.get(Snapshot, job.target_id)
                repo = db.get(Repository, snapshot.repository_id)
                snapshot.status = 'INDEXING'
                db.commit()
                rows, skipped = [], []
                for path, text in source_objects(repo.id, repo.remote_url, snapshot.commit_sha):
                    try:
                        rows.extend(extract(path, text))
                    except SyntaxError:
                        skipped.append(path)
                    if len(rows) > 2000:
                        raise ValueError('Snapshot exceeds 2,000 chunks')
                if not rows:
                    raise ValueError('No readable Python or document evidence found')
                for start in range(0, len(rows), 32):
                    vectors = embeddings([r['content'] for r in rows[start:start+32]])
                    if vectors:
                        for row, vector in zip(rows[start:start+32], vectors):
                            row['embedding'] = vector
                db.execute(delete(Chunk).where(Chunk.snapshot_id == snapshot.id))
                db.add_all([Chunk(snapshot_id=snapshot.id, **r) for r in rows])
                snapshot.status = 'READY'
                snapshot.stats = {'chunks': len(rows), 'files': len({r['path'] for r in rows}),
                                  'syntax_errors': skipped, 'embedding_model': settings.embedding_model or None,
                                  'retrieval': 'hybrid' if settings.embedding_model else 'lexical'}
            elif job.kind == 'INVESTIGATE':
                run = db.get(Investigation, job.target_id)
                ticket = db.get(Ticket, run.ticket_id)
                run.status = ticket.status = 'INVESTIGATING'
                db.commit()
                query = ' '.join([ticket.title, ticket.description, ticket.expected_behavior, ticket.actual_behavior])
                found = search(db, run.snapshot_id, query)
                from .retrieval import similar_tickets
                history = similar_tickets(db, ticket)
                traces = [{'filename': a.filename, 'content': a.content[:4000], 'hash': a.content_hash}
                          for a in db.scalars(select(Attachment).where(Attachment.ticket_id == ticket.id).limit(5))]
                run.diagnosis = {**investigate(ticket, [c for c, _ in found], history, traces), 'similar_tickets': history}
                run.evidence_ids = [c.id for c, _ in found]
                run.status = 'COMPLETED'
                ticket.status = 'DIAGNOSED' if run.diagnosis['hypotheses'] else 'ESCALATED'
            else:
                raise ValueError('Unknown job kind')
            # Fence a stale worker from committing results after its lease was reclaimed.
            fenced = db.execute(update(Job).where(Job.id == job.id, Job.attempts == attempt, Job.status == 'RUNNING')
                                .values(status='COMPLETED', lease_until=0))
            if fenced.rowcount != 1:
                db.rollback()
                return True
            db.add(AuditEvent(project_id=job.project_id, actor='worker', action=f'{job.kind}_COMPLETED', target_id=job.target_id))
            db.commit()
        except Exception as exc:
            db.rollback()
            # Do not store provider responses, URLs with credentials, or source in logs/errors.
            log.warning('Job %s failed (%s)', job.id, type(exc).__name__)
            current = db.get(Job, job.id, populate_existing=True)
            if current.attempts != attempt:
                return True
            current.status = 'FAILED'
            current.error = 'Operation failed. Check Git access, source validity, quotas and model configuration; then submit a new job.'
            if job.kind == 'INDEX':
                db.get(Snapshot, job.target_id).status = 'FAILED'
            else:
                run = db.get(Investigation, job.target_id)
                run.status = 'FAILED'
                db.get(Ticket, run.ticket_id).status = 'ESCALATED'
            db.add(AuditEvent(project_id=job.project_id, actor='worker', action=f'{job.kind}_FAILED', target_id=job.target_id))
            db.commit()
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if not run_once():
                time.sleep(settings.worker_poll_seconds)
        except Exception:
            log.exception('Worker polling failed')
            time.sleep(5)


if __name__ == '__main__':
    main()
