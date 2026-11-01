# BugHound-Ai — Autonomous Agentic AI Issue Diagnosis

A working React/TypeScript + FastAPI investigation workspace for Python software issues.
Customers submit reports; engineers index an immutable Git commit, run an asynchronous
investigation, and inspect source evidence with exact line ranges and SHA-256 hashes.

**Current delivery:** Phase 1/2 development implementation with an integrated local demo.
The full 50% milestone is **not yet signed off**: real model/embedding credentials,
an OIDC identity provider, and PostgreSQL deployment verification remain outstanding.
The default demo performs lexical source retrieval, not LLM root-cause reasoning.

## Run on Windows

Prerequisites: Python 3.13, Node.js 22+, Git. Open PowerShell in this folder:

```powershell
./scripts/setup.ps1
./scripts/start.ps1
```

Open <http://127.0.0.1:8000>. API documentation: <http://127.0.0.1:8000/docs>.
Use **Enter as customer** for reports, **Enter as engineer** for investigations,
or **Administrator workspace** to connect repositories. Demo authentication must
remain on loopback and must never be exposed as production authentication.

The setup script seeds three intentionally buggy Python examples and queues their
indexing. The start script runs the API and worker together; Ctrl+C stops both.
Data is persisted in `data/app.db`. Re-running setup does not duplicate seed records.

For source development, run the API and worker separately from the repository root:

```powershell
$env:PYTHONPATH='apps/api'
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# In another terminal, set PYTHONPATH again:
.venv/Scripts/python -m app.worker
# In a third terminal:
cd apps/web
npm run dev
```

The production build is served by FastAPI. Vite proxies `/api` in development.

## Demonstrate the vertical slice

1. Sign in as customer and create an issue with expected/actual behavior and steps.
2. Sign out and enter as engineer. Open the issue from the queue.
3. Select the ready `python-support-service` snapshot and run an investigation.
4. Wait for completion. Inspect candidate hypotheses and click an evidence link.
5. Check the pinned commit, source path, symbol, exact lines and source hash.
6. Inspect durable jobs and audit events in Activity.
7. Re-enter as customer: the report/status is visible, internal code is not.

For a real Python repository, use the administrator repository screen, register
an authorized credential-free HTTPS Git URL and index its **exact 40-character SHA**.
GitHub and GitLab are allowlisted by default. Local repositories must be under
`LOCAL_REPO_ROOT`. Private provider authentication is not implemented yet; do not
put credentials in URLs. Git objects are read without executing repository code.

## Configure real integrations

Copy `.env.example` to `.env`; keep `.env` untracked. The application reads it at startup.

- Set `MODEL_MODE=live`, `MODEL_BASE_URL`, `MODEL_API_KEY`, and `MODEL_NAME` for a
  compatible `/chat/completions` JSON-response endpoint. Live mode sends selected
  source snippets and report text to that provider. Choose an authorized provider.
- Set `EMBEDDING_MODEL` for a compatible `/embeddings` endpoint returning 1536
  dimensions. Index a fresh snapshot after changing an embedding model.
- Set `AUTH_MODE=oidc`, issuer, audience and HTTPS JWKS URL. JWT validation checks
  RS256 signature, issuer, audience and required expiry/issued-at/subject claims.
  Set `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URI` and provider-specific `OIDC_SCOPE` (including
  your API scope where required). Register that exact redirect URI at the provider.
  Provision project memberships for verified OIDC subjects before sign-in. The
  browser uses authorization code + PKCE; tokens stay in memory and only transient
  redirect state uses session storage. Real provider acceptance is still required.

Without embedding configuration, the UI explicitly says **lexical retrieval**.
Without live model configuration, the UI explicitly says **retrieval-only demo**.
No generated patch, autonomous merge, or production deployment exists in this phase.

Operators can provision membership from the repository root after migrations:

```powershell
$env:PYTHONPATH='apps/api'
.venv/Scripts/python -m app.admin create-project --tenant-id YOUR_TENANT --name "Your project"
.venv/Scripts/python -m app.admin grant-role --project-id PROJECT_ID --subject VERIFIED_OIDC_SUBJECT --role engineer
```

Use the exact subject verified by your identity provider. This CLI requires direct
database/operator access; the public API does not allow self-assignment of roles.

## PostgreSQL + pgvector development stack

Start Docker Desktop. Add a URL-safe `POSTGRES_PASSWORD` to `.env`, then:

```powershell
docker compose up --build -d
docker compose exec api python -m app.seed
```

Compose runs PostgreSQL/pgvector, a one-shot Alembic migration, the API and a separate
durable worker. The API is bound to `127.0.0.1:8000`; the database has no host port.
The SQLite process must be stopped first because it uses the same API port.
This stack has been supplied but was not run on the delivery machine because its
Docker engine was unavailable. Treat production deployment as a separate acceptance gate.

## Verification

```powershell
.venv/Scripts/python -m pytest -q -p no:cacheprovider
cd apps/web
npm test
npm run build
npm audit
```

From the repository root after seeding/indexing:

```powershell
$env:PYTHONPATH='apps/api'
.venv/Scripts/python scripts/evaluate.py
```

The evaluation writes `output/evaluation.json`. It measures source localization on
three synthetic examples only, not causal diagnosis accuracy or production success.
GitHub Actions runs backend tests/migrations and frontend tests/build/audit on push
or pull request. A workflow file is supplied; no remote CI run is claimed.

## Implementation map

- `apps/api/app/main.py`: REST API, request IDs, error envelopes, authorization,
  idempotent creation and public/internal projections.
- `apps/api/app/db.py`: relational entities and session management.
- `apps/api/app/indexer.py`: restricted Git ingestion, AST metadata, source hashes.
- `apps/api/app/retrieval.py`: lexical ranking, optional semantic fusion, scoped history.
- `apps/api/app/investigator.py`: versioned constrained prompt and validated output.
- `apps/api/app/worker.py`: persisted jobs, atomic claims, leases and failure handling.
- `apps/api/migrations`: frozen versioned schema migration.
- `apps/web/src`: customer/engineer/admin portal and evidence explorer.
- `docs/DELIVERY.md`: scope, acceptance evidence, limitations and next steps.

## Boundaries

This is a development system, not a hardened enterprise release. Authorization is
enforced on every project resource in the API. PostgreSQL row-level security, a
dedicated organization/user administration model, encrypted artifact storage,
binary attachment storage, notifications, cancellation, database backups and
load/security testing remain future work. Secret-pattern filtering is best effort,
not a guarantee that arbitrary repository source is safe to disclose to an AI model.
Git clone execution has a timeout; strict disk/process isolation for hostile or huge
repositories still requires infrastructure resource controls.

See `docs/DELIVERY.md` before calling the planned 50% milestone accepted.
