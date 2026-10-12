# Yoyo

Local company intelligence ledger: Apple TTML/JSON → normalization → OpenAI extraction → exact evidence checks → classification → lookup/resolve → synchronous enrichment → Postgres → React.

## Start

```sh
# Create .env from .env.example only if it does not already exist.
# Set OPENAI_API_KEY, MODEL, EXA_API_KEY and optionally LANGSMITH_API_KEY.
docker compose up -d --wait
uv sync
uv run alembic upgrade head
uv run uvicorn yoyo.api:app --host 127.0.0.1 --port 8000
# Separate terminal:
pnpm --dir web install --frozen-lockfile
pnpm --dir web dev
```

- Dataset: http://localhost:5173
- pgAdmin: http://localhost:5050 → Yoyo local → Databases → yoyo → Schemas → public → Tables. Refresh the Tables node after migration. The six application tables sit alongside Alembic's version table. Local database password: `yoyo_local`.
- API: http://localhost:8000/docs
- Traces: https://smith.langchain.com → `yoyo-local`, or open a run's trace link in the dataset viewer.

## Process a real transcript

```sh
uv run python -m yoyo /path/transcript.ttml \
  --metadata /path/metadata.json --episode-id APPLE_EPISODE_ID --max-calls 30
```

JSON uses Apple `segments[{start,end,text,speaker,words}]`, in seconds. Metadata includes episode ID, title, durationSeconds, releaseDate and itunesUrl when known. Raw originals are copied into ignored, hash-addressed `artifacts/`; nothing depends on a committed dataset. MODEL is a configured OpenAI model ID, not a provider-prefixed string.

There are no recorded model fixtures, default episodes, seed commands or canned research results. Unit tests construct small adversarial inputs solely to exercise validation. The active dataset was reset for the live resolution run; the prior database is backed up locally. Evaluation controls are explicitly labeled and never supply expected answers to the resolver.

## Recovery and limits

Completed identical input/model/prompt runs reuse saved results without another model call. Add `--resume RUN_ID` to continue a failed run with identical arguments. Completed operations reuse their saved real responses. Submitted operations with unknown outcomes stop for inspection instead of silently sending again; no automatic job reconciliation is claimed.

Each operation saves input, raw response, response ID, usage and parsed output. The extraction/classification call budget and per-response token caps are enforced. Resolution has a finite per-mention workflow but does not yet share the global call budget. Actual dollar cost stays unknown until pricing/accounting is added. The OpenAI client disables automatic retries. A session advisory lock prevents concurrent identical runs; a transaction lock protects ledger writes. Claims and run results share one transaction; researched companies commit sequentially before the next mention.

Exact source text, speaker labels and numbers are checked. Company names can receive an exact quoted context segment; uniquely matching quote locators can be corrected without editing quote text. These checks do not prove entailment, completeness, true identity or factual accuracy. All model claims need review. Some supported paraphrases will be conservatively rejected.

Company mentions must pass lookup → resolve → commit. The default `--matching lexical` uses identifier/name candidates and an LLM decision; `--matching hybrid` adds cosine candidates and remains experimental. Only NEW_COMPANY triggers synchronous Exa research, followed by identity rechecking before commit. Unknown fields remain null. Sectors/products/brands are excluded; uncertain identities and affected claims are withheld in run artifacts. Subsidiaries remain distinct companies. People remain episode-scoped.

Both retrievers currently scan the small local ledger; indexed retrieval, asynchronous enrichment, discovery agents and the human-reviewed 10–20 episode benchmark remain future work. Changing extraction prompts may produce separate claims; exact completed-run replay is deduplicated.

LangSmith is optional operational diagnostics, not the evidence store. Traces contain IDs, artifact references, usage and commit counts; raw model text and complete transcripts stay in local artifacts (and are submitted to the configured model provider for processing). A trace failure does not invalidate committed research.

## Checks

```sh
uv run pytest -q
uv run alembic check
uv run ruff check --isolated --select E4,E7,E9,F yoyo tests migrations
pnpm --dir web build
```

Tests use isolated PostgreSQL schemas. Source, test, prompt and migration files stay under 250 lines; generated dependency lockfiles are exempt.

Run the real-provider comparison with `uv run python -m evaluation.compare evaluation/cases.jsonl --label YOUR_FRESH_LABEL`, then `uv run python -m evaluation.report YOUR_FRESH_LABEL`. Each method starts in its own empty database schema and shares a durable cache of real provider responses. See [matching results](docs/matching-comparison.md).

See [schema](docs/schema.md), [reused code](docs/reuse.md), and [verification](docs/verification.md).
