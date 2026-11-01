import math
import re
from collections import Counter
import httpx
from sqlalchemy import select
from .config import settings
from .db import Chunk, Snapshot, Ticket


def tokens(text):
    return re.findall(r'[a-z0-9]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', text).lower())


def similar_tickets(db, ticket, limit=3):
    """Historical customer reports are context, never verified root-cause evidence."""
    terms = set(tokens(ticket.title + ' ' + ticket.description))
    candidates = db.scalars(select(Ticket).where(Ticket.project_id == ticket.project_id, Ticket.id != ticket.id).order_by(Ticket.created_at.desc()).limit(500))
    ranked = []
    for candidate in candidates:
        other = set(tokens(candidate.title + ' ' + candidate.description))
        score = len(terms & other) / max(1, len(terms | other))
        if score >= .15:
            ranked.append((score, candidate))
    return [{'ticket_id': t.id, 'title': t.title, 'status': t.status, 'context_only': True}
            for _, t in sorted(ranked, key=lambda item: item[0], reverse=True)[:limit]]


def embeddings(texts):
    if not settings.embedding_model:
        return None
    if settings.embedding_dimensions != 1536:
        raise ValueError('This schema requires 1536-dimensional embeddings')
    with httpx.Client(timeout=45) as client:
        response = client.post(settings.model_base_url.rstrip('/') + '/embeddings',
                               headers={'Authorization': f'Bearer {settings.model_api_key}'},
                               json={'model': settings.embedding_model, 'input': texts, 'dimensions': 1536})
        response.raise_for_status()
        rows = sorted(response.json()['data'], key=lambda r: r['index'])
    vectors = [r['embedding'] for r in rows]
    if len(vectors) != len(texts) or any(len(v) != 1536 or not all(math.isfinite(n) for n in v) for v in vectors):
        raise ValueError('Invalid embedding response')
    return vectors


def search(db, snapshot_id, query, limit=8):
    chunks = list(db.scalars(select(Chunk).where(Chunk.snapshot_id == snapshot_id)))
    if not chunks:
        return []
    terms = set(tokens(query))
    docs = [Counter(tokens(c.symbol + ' ' + c.path + ' ' + c.content)) for c in chunks]
    average = sum(sum(d.values()) for d in docs) / len(docs)
    scores = []
    for c, doc in zip(chunks, docs):
        score = 0.0
        for term in terms:
            frequency = doc[term]
            df = sum(term in d for d in docs)
            idf = math.log(1 + (len(docs) - df + .5) / (df + .5))
            score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * sum(doc.values()) / max(average, 1)))
        if c.symbol != '<module>':
            score *= 1.15
        if score > 0:
            scores.append((c, score))
    exact = sorted(scores, key=lambda x: x[1], reverse=True)
    fused = {c.id: 1 / (60 + i) for i, (c, _) in enumerate(exact, 1)}
    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot.stats.get('embedding_model') and snapshot.stats['embedding_model'] != settings.embedding_model:
        raise ValueError('Embedding model changed; index a fresh snapshot before semantic retrieval')
    if snapshot.stats.get('embedding_model'):
        vector = embeddings([query])[0]
        if db.bind.dialect.name == 'postgresql':
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import cast
            semantic = list(db.scalars(select(Chunk).where(Chunk.snapshot_id == snapshot_id, Chunk.embedding.is_not(None))
                                      .order_by(cast(Chunk.embedding, Vector(1536)).cosine_distance(vector)).limit(30)))
        else:
            def cosine(c):
                a = c.embedding
                return sum(x*y for x, y in zip(a, vector)) / max(1e-12, math.sqrt(sum(x*x for x in a)*sum(y*y for y in vector)))
            semantic = sorted((c for c in chunks if c.embedding is not None), key=cosine, reverse=True)[:30]
        for i, c in enumerate(semantic, 1):
            fused[c.id] = fused.get(c.id, 0) + 1 / (60 + i)
    ranked = sorted((c for c in chunks if c.id in fused), key=lambda c: fused[c.id], reverse=True)
    return [(c, round(fused[c.id], 6)) for c in ranked[:limit]]
