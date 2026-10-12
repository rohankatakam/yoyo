# Milestone 1 verification — 2026-10-12

Verified on the local checkout with Docker Postgres 17 and pgAdmin 9, Python 3.11, and the committed dependency locks.

- `uv run pytest -q`: 7 passed. Covers exact replay, concurrent replay, source-version evidence, invalid quotes/speakers, transaction rollback and retry, source corruption, API traceability, and observability outage isolation.
- `uv run alembic upgrade head` and `uv run alembic check`: initial migration applies; no model/schema drift.
- `pnpm --dir web build`: TypeScript check and production build pass.
- First reference import saved 1 company, 1 person, 1 source excerpt, 2 passages, 2 proposals, 2 claims, 2 evidence links and 1 identity decision.
- Second import saved zero additional research records. Two independent run attempts remain in history.
- Real Postgres container restart and API process restart: company ID, counts and evidence persisted; React reloaded successfully.
- Browser inspection: company/detail view, search empty state, expanded provenance and run history work. Stored JSON is hash-checked by the API.
- pgAdmin: connected to `Yoyo local`, selected `yoyo`, ran the join below and observed both Felins claims with their exact quotes, timestamps and speaker labels.
- LangSmith project `yoyo-local`: both root runs and their `validate_and_commit_findings` child spans were read back through the authenticated API, with completion timestamps and no errors. The in-app browser reached the sign-in page, so authenticated visual trace inspection remains user-side.
- API key remains in ignored `.env`; it is not included in source, fixtures or trace payloads.

Local screenshots are in ignored `artifacts/verification/`.

```sql
SELECT c.name, cl.predicate, e.quote, p.start, p.speaker_label
FROM companies c
JOIN claims cl ON cl.company_id = c.id
JOIN evidence e ON e.claim_id = cl.id
JOIN passages p ON p.id = e.passage_id
ORDER BY p.start;
```

## Boundaries

The two reference findings are assistant-selected from an archived transcript, pending human review. They are not audio-verified, independently verified, or evidence of extraction accuracy. The complete episode was not processed. Real speaker identities, external entity identifiers, enrichment, automatic recovery of interrupted run attempts, model extraction and discovery are not implemented in this milestone. An API/database restart was tested; interruption during a transaction is covered by an injected failure test, not a process-kill test during a write.
