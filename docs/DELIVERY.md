# Phase 1/2 delivery record — 1 November 2026

## What is implemented

- React + TypeScript responsive portal: demo login, project selection, customer report
  form, paginated issue queue, status/history, internal investigation view, repository
  registration/indexing, retrieval workbench, source explorer, jobs and audit trail.
- FastAPI with persisted projects, project memberships, reports, repositories,
  snapshots, chunks, investigations, jobs, audit events and idempotency records.
- Application-enforced project/tenant boundaries and per-customer report ownership.
  Customer projections do not return diagnoses, source, repository metadata or hashes.
- Signed OIDC JWT verification backend, browser authorization code/PKCE login,
  in-memory access tokens and fail-closed configuration behavior.
- Up to five bounded .txt/.log attachments per issue, with automatic common-secret,
  private-key and email redaction before storage; sanitized traces can inform the
  investigator. No binary/PDF/image attachments are supported in this increment.
- Immutable 40-character commit pinning; Git objects are read without checkout or
  execution. Symlinks/submodules, hidden paths, generated folders, oversized files
  and obvious credential patterns are excluded from indexing.
- Python function/class/async/nested symbol extraction, imports, static call
  candidates, exact source lines, module chunks and Markdown/text documentation.
- Lexical retrieval with optional 1536-dimensional provider embeddings, reciprocal
  rank fusion and snapshot filtering. PostgreSQL uses pgvector cosine distance;
  SQLite is a local development fallback. Similar historical reports remain
  project-scoped, unverified context and never count as source evidence.
- Constrained live model adapter with structured validation, versioned prompt,
  evidence-ID checks and hash checks. Missing/failing providers fail the job; there
  is no silent fallback that pretends an LLM ran.
- Durable database queue with atomic claims, retry limits for interrupted workers,
  lease expiry/recovery, failure states and audit recording. Routine failed model
  calls are escalated rather than automatically repeated at unknown cost.
- Alembic migration, pinned dependency lockfiles, local start/setup scripts,
  PostgreSQL Docker Compose stack and GitHub Actions workflow.

## Verified locally

The customer/engineer API-to-worker-to-source-evidence journey was exercised in a
browser against the real local backend. The fixture Git repository was actually
indexed. Source evidence shows its actual commit and Python line references.

Backend tests cover the integrated pipeline, customer source privacy, cross-tenant
reads/retrieval, same-project customer ownership, idempotency conflicts, malformed
input, nested/async AST extraction, unsafe Git URLs, model failures, unknown model
references, tampered source, interrupted/exhausted job recovery, signed JWT validation,
semantic snapshot isolation and historical-ticket isolation.

21 backend tests pass, including attachment redaction/quotas. Four frontend tests
pass, covering customer report access, the queued-investigation state and SSO setup.
The production frontend build passes. Dependency audit was brought to zero reported
npm vulnerabilities. The three-case localization smoke benchmark found the expected
function at rank 1 for all three fixtures; this tiny fixture is not a general accuracy claim.

## Required before accepting the full 50% milestone

1. Choose and configure the live model and embedding deployment, verify data-handling
   authorization, and run real model/semantic retrieval against a representative
   authorized Python repository. The supplied GitHub project currently contains only
   its README/license at the baseline, so the seeded Python service is the demo target.
2. Start Docker and verify migrations, pgvector queries, API/worker sharing and restart
   behavior against PostgreSQL. This machine did not have a running Docker engine.
3. Configure the real OIDC issuer/audience/JWKS and client ID, register the callback,
   provision memberships, and verify redirect/PKCE with the selected provider.
4. Review attachment redaction against real sanitized support logs. Text/log uploads
   are implemented; add binary formats only if the agreed review scope requires them.
5. Expand localization evaluation beyond three synthetic fixtures and record the
   agreed acceptance threshold. Exercise a private-repository integration if needed.
6. Push the reviewed branch and verify remote CI. No remote push/CI/deployment was
   performed as part of the local implementation.

The planned percentage is an acceptance milestone, not a measured fraction of lines
of code. This delivery is a working implementation toward 50%, not a claim that all
Phase 1/2 acceptance criteria have already passed.

## Phase 3 next

Independent evidence auditor; bounded reasoning retries; minimal diff/test generation;
diff allowlist policy; isolated baseline/regression/full-suite execution; review UI.
Do not allow patch generation until independent audit passes. Do not label tickets
resolved until an external release is confirmed.

## Operational limitations

- SQLite is for one-machine development. Indexing quotas bound parsed text, not
  download size; use OS/container resource limits for untrusted remote repositories.
- Jobs reclaim expired leases after one hour, with at most three interrupted-worker
  attempts. There is no dedicated heartbeat, cancellation or distributed tracing yet.
- Python syntax errors are recorded and skipped; a source match is not proof of a bug.
- Model and embedding calls use one compatible endpoint/key, with 1536-dimensional
  embeddings fixed in this schema. Provider-specific Azure routing is not implemented.
- Secrets filtering is heuristic. Review repositories and provider permissions before
  enabling live model transmission. Credentials are environment configuration only.
- Repository credentials, organization administration, RLS, binary artifact storage,
  retention, alerts, cost accounting and deployment hardening remain pending.
- External API failures expose only generic job errors. Operator logs record the
  exception class and job identifier, not source or provider response bodies.

## Reference documentation used during implementation

- [FastAPI SQL databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [SQLAlchemy select and locking API](https://docs.sqlalchemy.org/en/20/core/selectable.html)
- [PyJWT verification API](https://pyjwt.readthedocs.io/en/latest/api.html)

Source blueprint: user-supplied `Autonomous_Agentic_AI_Complete_Project_Plan.pdf`,
especially the Phase 1 and Phase 2 deliverables and review gates. The PDF is reference
material; its embedded recommendations were not treated as independent user commands.
