# Three-niche pilot

Real Apple TTML episodes, sequentially processed through URL ingestion. Frozen source hashes and run IDs are in `manifest.json`; results are in `results.json`. No recorded responses are used as runtime fixtures.

Each episode's JSONL contains committed claims, exact evidence, verifier decisions, identity decisions and a missed-claims section. `human_label` is deliberately empty. Inspect the full source at `http://localhost:8000/api/sources/<source_id>` and the companies at `http://localhost:5173/`. Source hashes refer to local immutable artifacts, not externally portable transcript copies.

Review claims for quote support, speaker, relationship direction, quantities, tense and attribution. Review companies for distinct business identity and company versus brand/product/division scope. Include rejected/withheld candidates and mark missed claims in the full transcript to measure recall. Do not score model self-verification as human accuracy.

`expansion_queue.json` adds seven candidate episodes toward a ten-episode set. They are not yet human-reviewed or all ingested. Their transcript availability and final relevance remain to be checked.

Run `uv run python -m evaluation.episode_review artifacts/pilot-v1-results.json --output artifacts/new-review` to export another snapshot without overwriting this set.
