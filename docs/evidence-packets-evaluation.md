# Evidence packets and verification — 2026-10-12

**Outcome: known domain/claim failures are caught; overall identity matching has not improved.**

| Metric | Previous lexical gate | New gate, no episode metadata | New gate, with episode metadata |
| --- | ---: | ---: | ---: |
| Expected decisions | 17/24 | 16/24 | 17/24 |
| Incorrect merge groups | 0 | 0 | 0 |
| Duplicate entity groups | 0 | 0 | 0 |
| Unresolved | 8 | 9 | 7 |
| Out-of-scope acceptance against fixed labels | 0 | 0 | 1 |
| Unique LLM input tokens | 379,659 | 548,694 | 569,792 |

## What changed

- Identity packets carry up to three target occurrences with complete adjacent transcript segments, speaker labels and timestamps. Episode title, description/show notes, candidate links, source URL, retrieval date and original-description hash are separate supplementary context. Long descriptions are filtered and capped; the original is retained in the source snapshot.
- Target transcript text is retained in research queries. New companies still receive synchronous Exa enrichment. LinkedIn URLs must match their cited source URL, rather than merely have the right shape.
- Proposed matches receive an independent two-entity check before acceptance. It catches decisions whose selected company conflicts with their own explanation. Disagreement is withheld, not automatically converted to a new company.
- Proposed primary domains receive an independent corporate-scope check. Regional/subsidiary/unknown websites remain observations in identity evidence, with the primary domain left unknown. This does not infer a replacement global domain.
- Claims receive a separate entailment check from original transcript evidence. No show notes, web enrichment or extractor rationale enters that check. INSUFFICIENT_CONTEXT gets one expansion from adjacent segments to five segments on each side. Only SUPPORTED proceeds; rejected claims are retained, not rewritten.
- Packets, provider responses, decisions and rejected claims remain in local artifacts/run progress; LangSmith links to operational traces. No additional service or schema migration was required. All authored Python files remain under 250 lines.

## Fixed comparison outcomes

Microdryd and MicroDry now resolve to one MicroDried company in the metadata arm. However, Walmart and Starbucks become unresolved, and Crispy Greens is accepted despite the fixed benchmark's brand-exclusion label. That label tests our conservative scope policy; it is not proof that no corresponding company exists. The Meta/Facebook controls also still fail the intended creation-then-alias sequence. These are offsetting changes, not an overall win.

Episode metadata contains other businesses and promotional language. The independent check still confused Walmart with the episode's focal company, BranchOut, despite the target being explicit. Show notes are useful evidence but can also distract the model. More context is not automatically better.

| Mention | Expected | Previous | New with metadata |
| --- | --- | --- | --- |
| BranchOut Food | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Nasdaq | NOT_COMPANY | UNRESOLVED | UNRESOLVED |
| natural food space | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| snack food industry | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Costco | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Walmart | NEW_COMPANY | NEW_COMPANY | UNRESOLVED |
| Microdryd | NEW_COMPANY | UNRESOLVED | NEW_COMPANY |
| Crispy Greens | NOT_COMPANY | NOT_COMPANY | NEW_COMPANY |
| BranchOut | MATCH | MATCH | MATCH |
| N-Wave | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Starbucks | NEW_COMPANY | NEW_COMPANY | UNRESOLVED |
| MicroDry | MATCH | UNRESOLVED | MATCH |
| Alphabet Inc. | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Google LLC | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Google Chrome | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Mercury | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Mercury | NEW_COMPANY | UNRESOLVED | NEW_COMPANY |
| Mercury | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Meta Platforms | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Facebook | MATCH | NEW_COMPANY | NEW_COMPANY |
| Crispy Fruit | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Branch Out Food | MATCH | MATCH | MATCH |
| Sow Good Inc. | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| the supplier | UNRESOLVED | UNRESOLVED | UNRESOLVED |

## Claim and domain checks

The same **19 structurally accepted extracted claims** were evaluated without re-extraction. Fifteen passed; four were withheld (three INSUFFICIENT_CONTEXT, one OVERSTATED). This is acceptance behavior, not a measured precision/recall score.

- The known Starbucks error (“got our product in front of Starbucks” → “secured product placement”) is now withheld.
- The verifier also withheld Walmart private-label supply, branded-product retail sales and a growth explanation. At least some appear conservatively rejected despite plausible surrounding support; a human-reviewed reference set is needed to measure false rejections.
- One bounded expansion rescued the three-pronged strategy claim after the initial local context was insufficient.
- The previously saved `starbucks.com.sg` domain was independently tested against saved sources and rejected as regional. No unsupported global replacement was written. This verifies one known failure, not general domain accuracy.

## Evaluation limits and overhead

Both final matching arms began with empty isolated PostgreSQL ledgers, used the same 24 cases/order, model and final code, and shared a cache of actual provider responses. Twelve cases are actual episode mentions; twelve are explicitly authored controls. Episode metadata is added only to the real episode cases. This comparison tests title/description/links together, not show-note text alone.

The previous 17/24 is the saved earlier implementation result. The two new arms form the controlled comparison. Development pilots exposed and corrected dropped search context, contradictory matches and unconstrained citation references. Their intermediate/mixed-version results are excluded. Some overlapping pilot requests stopped at an in-flight cache entry instead of duplicating submissions; final runs completed sequentially.

This is a development set used while improving the implementation, not held-out validation. Wider context changes downstream research and ledger contents, so individual gains cannot all be attributed to specific words in the description.

Research input tokens rose about 50% versus the previous gate. Adding metadata to the new gate increased input tokens about 4%. Shared cache hits invalidate observed elapsed times as latency comparisons. Claim verification adds one call per claim plus at most one context expansion. These checks still do not share the extractor's global call budget.

## Recommendation

Keep claim and domain checks, with rejection review. Treat show-note-assisted matching as experimental: overall decision agreement is unchanged and one brand-policy regression remains. Next, pass only target-relevant note passages and resolve conflicts with focused evidence; then evaluate on new, human-reviewed episodes. Do not add another retrieval system based on these results.

## Reproduce and inspect

Run `python -m evaluation.prepare_packets RUN_ID` to snapshot a saved episode and its extracted claims. Run `evaluation.compare` with the generated `artifacts/packet-no-notes-cases.json` and `artifacts/packet-notes-cases.json`, using distinct fresh labels and `--mode lexical`. Run them sequentially. `python -m evaluation.verify_saved` evaluates the saved claims.

Final matching artifacts: `artifacts/packets-{without,with}-notes-final-lexical.json`; summary: `artifacts/evidence-packets-summary.json`; claim verdicts: `artifacts/packet-claim-verification-v2.json`; domain check: `artifacts/packet-domain-verification.json`. Artifacts are local and ignored by Git; no API keys or raw provider responses are committed.

Integrated replay: 19 unchanged extracted claims → 15 passed entailment → 11 committed claims, 4 companies, 28 evidence rows and 43 sources. Companies: BranchOut Food Inc., Costco Wholesale Corporation, MicroDried, Walmart Inc.. Inspect in pgAdmin under schema `eval_20b294e7ce86`; run `93fc538b-0c89-4355-9e14-254e55a26034`. The active public dataset was not overwritten. [Hosted trace](https://smith.langchain.com/o/5df0febc-a638-5587-b034-94cf8f8de68c/projects/p/eaa468f4-bc8f-4277-ad07-900efef44439/trace/830aa48d-1e74-4cb8-90db-63c6f038392a/run/830aa48d-1e74-4cb8-90db-63c6f038392a?start_time=2026-10-13T00%3A41%3A46.490464%2B00%3A00) was read back with an end time and no error.

Checks: 33 tests passed; Ruff passed; no Alembic drift; all authored Python files remain under 250 lines.
