# Next milestone after the evidence-packet checkpoint

Recommendation: preserve the current implementation, make one bounded identity-context correction, then broaden fixed-episode evaluation. Do not continue open-ended tuning on the same 24 development cases or call 17/24 human-reviewed accuracy.

Sources reviewed:
- [Podcast Agent architecture](https://app.notion.com/p/3f7072fbbd9880539bc5f0ee42d407b5)
- [Podcast agent evaluation](https://app.notion.com/p/3f7072fbbd98804ea16dce9238234db3)

## Current position

The local ledger, raw evidence storage, transcript normalization, extraction, company lookup, synchronous Exa enrichment, verification, commit path, React viewer, pgAdmin and LangSmith diagnostics exist. The 24-case regression set is now versioned under `evaluation/identity_v1`. Claims/domain checks catch known failures, but identity decision agreement remains 17/24, metadata introduces a scope regression, and research input tokens increased about 50%.

We have not yet implemented the architecture's complete Apple discovery/retrieval tools, coverage/history selection, shared nested-call budget, LangGraph checkpointer or bounded `create_agent` loop. The document names Parallel; the current Exa adapter is an implementation choice, not a reason to add a second provider before measuring a need.

## Order of work

1. **One stabilization pass:** pass only target-relevant note excerpts and make the target/counterparty distinction explicit. Review provisional labels, especially brand versus company. Keep parent/subsidiary separation and unresolved outcomes. Compare against identity-v1; do not change labels merely to improve scores. Require no false merges or new scope regressions on reviewed cases, and report abstentions and cost separately.
2. **Next functional slice:** episode URL → episode metadata/show notes → existing transcript retrieval → current processing gates → committed database-derived results. Add `get_episode`, `ensure_transcript(existing_only)` and `read_source` around the existing functions. Introduce shared persisted call/time/spend accounting before dispatch, covering nested verifier and enrichment calls. No paid transcription fallback in this first slice.
3. **Broaden fixed testing:** select three new episodes, one per contrasting niche, with repeated companies and ambiguous identities; preserve them as held-out from prompt tuning. Human-review extraction and identity evidence. Expand to the Notion target of 10–20 episodes. Test repeated input, interrupted work and trace recovery from a fresh process. Missing transcripts and unresolved identities must remain explicit outcomes.
4. **Then discovery and the bounded agent:** add Apple search/feed listing and a database-derived coverage/history snapshot. Wrap the tested tools with the document's `create_agent` plus Postgres checkpointer. Enforce budgets outside model control, resume saved operations, and derive final saved IDs/counts/costs from storage. Begin live discovery only after fixed-episode behavior is measured.

The 24-case set is a regression baseline, not the entire evaluation plan. Financial amounts remain optional and must retain their type, currency, date, basis and evidence; unknown is acceptable. Async enrichment, scheduled workers and additional infrastructure can wait until synchronous runs establish useful yield and recovery behavior.

These are recommendations; this checkpoint does not implement the next milestone or change the Notion pages.
