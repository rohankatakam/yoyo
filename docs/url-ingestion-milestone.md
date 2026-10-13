# URL ingestion and bounded discovery checkpoint

## Delivered

- Target-name pair check and relevant show-note excerpts, including only links in those excerpts. Frozen 24-case development regression: 17/24 → 18/24 against unchanged provisional labels; zero observed incorrect merges/duplicate entities. See [targeted regression](../evaluation/target_fix_v1/README.md).
- Apple episode URL → public catalog metadata (authorized Apple catalog fallback) → downloaded or Apple-hosted TTML → existing normalization/extraction/verification/resolution/enrichment pipeline → PostgreSQL. No transcription submission.
- One persisted external-call allowance and deadline across catalog, extraction, verification, resolution, Exa enrichment, embeddings and planner calls. Completed responses cost no new call allowance. Unknown submissions remain charged and cannot silently retry. Calls run sequentially; planner turns and episode counts are also bounded. Dollar spend is reported only where providers supply it; no hard USD cap is claimed.
- `create_agent` with typed coverage, discovery and ingestion tools. Search reason, date, results and exhausted-window status live in `runs.progress`; artifact bodies remain immutable local files. Same-day query history is reused and processed-episode flags are recalculated. A new explicit run gets a fresh LangGraph thread; `--resume` uses the saved thread/settings/budget. IDs and counts come from the database.
- PostgreSQL checkpoint tables in `agent_checkpoints`; no new application tables, queue server or worker service. In pgAdmin refresh **Schemas → agent_checkpoints → Tables**. Existing six research tables remain in `public`.
- `/api/coverage`, existing React dataset viewer and verified hosted LangSmith traces.

## Three new episodes

| Niche | Episode | Structurally accepted | Model-supported | Saved claims | New companies | Processing external calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Food manufacturing | Blender Bites | 5 | 4 | 3 | 6 | 67 |
| Industrial automation | Honeywell | 5 | 4 | 3 | 1 | 21 |
| Healthcare services | Memorial Hermann | 18 | 18 | 13 | 1 | 40 |

19 saved claims, eight new companies and 46 evidence rows. Seven model-supported claims were withheld at identity resolution. Companies may be saved during sequential research even when their associated claim is later withheld; they are not all new qualified leads. The original five-company dataset remains, making 13 companies and 34 claims overall at this checkpoint.

These are pipeline yields, not precision/recall. Model support is not independent factual verification. Metadata/transcripts were acquired in a preflight; processing call counts exclude those preflight requests and reused provider responses. [Review inputs, outputs and source hashes](../evaluation/episodes_v1/README.md) are frozen with human labels unset. Seven additional candidate episodes form a queue toward ten; they are not all processed or reviewed.

## Verified operations

- All three identical URL reruns reused completion records: zero added companies, claims, evidence or sources.
- Injected an interruption after real transcript acquisition; a fresh Python process resumed the same ingestion run, reused the completed extraction run, made zero provider calls and made no duplicate writes.
- Unit/database tests cover shared nested budgets, unknown-outcome no-resubmission, cache hits, saved responses surviving an accounting failure, atomic claim-write rollback and concurrent identical-run locking.
- Live discovery-only agent completed; its persisted checkpoint resumed without repeating model calls after a result-formatting fix.
- Live discovery-to-ingestion found the Edgewater Healthcare Services interview. Apple returned a definitive transcript 404. The saved run is `waiting`, with no paid transcription and no new entities/claims. The original known 404 was reconciled without a repeat request. Unknown network outcomes remain blocked for inspection.
- A positive typed discovery → ingestion replay completed with zero ledger changes.
- A live zero-call run returned `budget_exhausted` before any provider dispatch.
- Pilot and agent LangSmith traces were read back from the hosted service. Raw transcripts, authorization headers and API keys are not committed.

During validation, checkpoint index setup exposed an old idle transaction in the advisory-lock connection. The connection now uses autocommit; the interrupted index was rebuilt and its validity checked.

Validation: 44 tests passed; Ruff, React production build and Alembic drift checks passed. All authored source files are at most 250 lines. The live coverage API returns the updated counts.

## Remaining quality and scale limits

Review retail banners versus legal companies (Real Canadian Superstore/Loblaws), hospital versus health-system scope, and Crispy Green versus Crispy Fruit before treating records as ground truth. Some valid claims are withheld because one party cannot be resolved. The six remaining identity-regression mismatches and provisional label adjudication are recorded; no further prompt-tuning loop was performed.

The full 10–20 episode human-reviewed benchmark, calibrated precision/recall, hard dollar spending limits, automatic reconciliation of uncertain requests, indexed entity retrieval and asynchronous enrichment remain unfinished. Existing-only transcription means missing transcripts wait; there is no background polling service. Coverage is observed ledger/search history, not a measured fraction of a complete market universe.
