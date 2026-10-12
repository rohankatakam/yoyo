# Milestone 2 verification — 2026-10-12

## Executed

- Backed up local PostgreSQL before migration (`artifacts/backups/before-six-tables.dump`). Rehearsed migration 0002 against copied existing tables inside an isolated transaction, then applied it. IDs, evidence quotes and passage counts reconcile. Migration 0003 removes a redundant uniqueness index on unbounded quote text; deterministic evidence UUIDs deduplicate writes.
- `pytest -q`: 23 passed. Tests cover invalid/missing/word/millisecond timing, exact quotes, native speaker labels, modality/numbers, grounded context, annotation evidence, typed optional financial data, atomic rollback, concurrent replay, source-version evidence, corrupt artifacts, unknown-outcome protection and resuming an interrupted run.
- `alembic check`: no schema drift. TypeScript and Vite production build pass. Ruff critical checks pass. All authored modules/tests/migrations/docs are at most 250 lines.
- Removed the recorded reference fixture and fixture-import command. No source episode, extracted research answer or model is hardcoded into runtime code. `.env` selects `gpt-4.1-mini-2025-04-14`.
- Real OpenAI Responses calls processed all 596 segments of the 3,263-second BranchOut Food Apple TTML episode `1000713465707`, with saved metadata. No mock model was used.
- Final run `185dd717-a07e-4400-9a4d-a731c265e4d0`: 24 structurally accepted claims, 78 evidence rows, 33 rejected candidates. Classifications: 9 forward-looking, 15 not forward-looking. This is not a human-scored accuracy result.
- 11 completed operations: 4 extraction, 3 correction, 4 classification. One additional optional correction failed with an unknown network outcome. It was not resubmitted. Resume reused completed operations and continued the remaining work; affected candidates stayed rejected.
- Known response usage: 107,397 input + 19,753 output = 127,150 tokens for that run. The unknown call may have additional usage. Dollar cost is intentionally null, not zero.
- An identical rerun reused the completed run with no provider calls or changes in database counts.
- Read back the hosted LangSmith trace and all 14 spans (root, model operations and commit). The original root records the interruption; the provider rejected rewriting its finished status. Future attempts now use separate trace IDs linked to the durable research run, so resuming does not overwrite a finished trace.
- Local browser verified company/detail rendering, classifications and exact source citations against the new API. API restart served persisted records. pgAdmin uses the same running database; see schema.md for the current query and table paths.

## Interpretation and remaining work

Earlier reference records and two earlier live attempts remain in history; the database total is not the final run's accepted count. Raw responses, rejected candidates, source snapshots, original TTML and operation state are durable ignored artifacts. The old reference importer is gone.

This run exposes unresolved aliases (BranchOut/BranchOut Food; Microdryd/MicroDry), model entity-type mistakes (industry descriptions treated as company mentions), and debatable temporal labels. They remain visibly unverified, not canonical researched companies. Exact quotes establish traceability, not semantic correctness. Human review and identity/claim adjudication are the next gate before enrichment or discovery.

No live provider retrieval, Exa/Parallel enrichment, Jev calls, autonomous LangGraph research loop or benchmark precision/recall is claimed. Exa/Parallel credentials are available only in ignored `.env` for that later scope. Tests use small synthetic inputs for invariants, never stored answers as a runtime fallback.
