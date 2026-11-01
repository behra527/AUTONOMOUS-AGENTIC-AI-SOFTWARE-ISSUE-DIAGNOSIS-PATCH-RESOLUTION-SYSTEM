"""Small localization smoke benchmark; does not measure causal diagnosis accuracy."""
import json
from pathlib import Path
from sqlalchemy import select
from app.db import Session, Repository, Snapshot
from app.retrieval import search

CASES = [
    ('PDF upload exceeds size limit ValueError', 'upload.py', 'validate_pdf_upload'),
    ('calculate total percentage discount subtotal incorrect', 'pricing.py', 'calculate_total'),
    ('display name profile missing key', 'users.py', 'display_name'),
]


def main():
    with Session() as db:
        repo = db.scalar(select(Repository).where(Repository.project_id == 'project-demo', Repository.name == 'python-support-service'))
        snapshot = db.scalar(select(Snapshot).where(Snapshot.repository_id == repo.id, Snapshot.status == 'READY')) if repo else None
        if not snapshot:
            raise SystemExit('Seed and index the demo repository first.')
        rows = []
        for query, path, symbol in CASES:
            found = search(db, snapshot.id, query)
            rank = next((i for i,(c,_) in enumerate(found,1) if c.path == path and c.symbol == symbol), None)
            rows.append({'query': query, 'expected': f'{path}:{symbol}', 'rank': rank, 'hit_at_3': rank is not None and rank <= 3})
        result = {'benchmark': 'three-fixture lexical localization smoke test', 'commit': snapshot.commit_sha,
                  'retrieval': snapshot.stats['retrieval'], 'cases': rows,
                  'hit_at_3': sum(r['hit_at_3'] for r in rows)/len(rows),
                  'limitations': 'Tiny synthetic fixture; not production accuracy, diagnosis quality, or patch success.'}
        Path('output').mkdir(exist_ok=True)
        Path('output/evaluation.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
