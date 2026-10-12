# Yoyo

Local company evidence ledger. First milestone: one archived episode excerpt → validated findings → Postgres → React evidence view, with pgAdmin and LangSmith.

## Run

Prerequisites: Docker Desktop, uv, Node.js and pnpm.

```sh
cp .env.example .env  # only if .env does not exist
# Set LANGSMITH_API_KEY in .env; never commit it.
docker compose up -d --wait
uv sync
uv run alembic upgrade head
uv run python -m yoyo import-reference
uv run uvicorn yoyo.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd web
pnpm install --frozen-lockfile
pnpm dev
```

- Dataset: http://localhost:5173
- Database GUI: http://localhost:5050 (preconfigured “Yoyo local”; database password `yoyo_local`)
- API documentation: http://localhost:8000/docs
- Traces: https://smith.langchain.com → project `yoyo-local`, or the run's direct trace link.

All local service ports bind to loopback. The development database credentials are local-only. LangSmith receives episode IDs, run metadata and counts; full transcripts and credentials are not trace inputs. LangSmith is hosted; the app, database and source files run locally.

## Verify

```sh
uv run pytest
pnpm --dir web build
uv run alembic check
uv run python -m yoyo import-reference
```

The second import must report zero research-record deltas. Import attempts remain in run history. Tests isolate their data in temporary Postgres schemas. Restart the API and database, reopen the company and source JSON, and check stable IDs and evidence. Use `docker compose stop` to stop services without deleting data; avoid `down -v` unless intentionally deleting the ledger.

## Evidence and identity limits

The tracked fixture contains two short, verbatim passages from an existing Apple transcript archive (episode 1000793292726), with original segment indices, timestamps, speaker labels and parent artifact hash. These are assistant-selected reference findings pending human review; audio and external identity were not independently checked. This is not an extraction evaluation or an autonomous research run. Episode title is a descriptive reference label. Canonical episode URL is unknown; the provider episode ID is retained.

Names are scoped to the episode until actual identity resolution is implemented. The CEO statement remains an attributed relationship; neither it nor the reported age becomes an independently verified fact. Speaker labels are preserved without guessing real identities. Domain, LinkedIn, sector, ownership, funding stage and valuation are unknown. No enrichment is inferred. Future financial observations must retain amount, currency, date, basis and evidence, with valuation, funding and acquisition price as distinct types.

## Architecture

`yoyo/contracts.py` defines typed input. `service.py` owns validation, artifact hashing and transactional commit. CLI calls the service; the read-only API exposes saved records. Later agent tools and workers will call this same service boundary.

Postgres holds research and run history. Hash-addressed JSON artifacts are immutable and checked before serving. Proposals, claims, evidence and identity decisions are separate tables. Claim IDs do not include source versions, so repeated evidence can attach to an existing assertion. Exact replay uses deterministic keys, Postgres constraints and an advisory write lock. Cross-episode resolution and semantic claim deduplication are deliberately deferred.

A research transaction atomically commits both findings and its completed run result. Failure rolls back research records and marks the run failed. An interrupted process may leave a running attempt and an orphan immutable artifact; rerunning is safe. Automatic reconciliation/checkpoints/provider-job recovery belong to the worker milestone. Each attempt gets a new run ID. Counts come from committed database writes; tracing failures never roll back those writes.

LangSmith traces are operational diagnostics; Postgres is the audit source of truth. No model or paid research-provider calls occur in this milestone. Trace hosting charges, if any, are outside the zero research-call cost.

## Next gates

1. Human review of the reference evidence and identity policy.
2. Fixed-episode extraction into proposals; same validation/commit boundary.
3. Entity resolution and supported enrichment.
4. 10–20 episode evaluation with predeclared thresholds.
5. Provider retrieval/jobs, budget accounting and interruption recovery.
6. `create_agent`, Postgres checkpoints and bounded live discovery.

No agent/checkpointer is created in this first milestone: there is no model loop to resume yet.

See [the milestone verification record](docs/verification.md) for executed checks and their limits.
