# Company matching comparison — 2026-10-12

Use option 2 (lexical candidates + LLM) for this prototype. Option 3 adds description embeddings, but its broader candidates produced three incorrect merges in this test.

| Measure | Option 2 | Option 3 |
| --- | ---: | ---: |
| Expected outcomes | 17/24 | 13/24 |
| Incorrect merge groups | 0 | 3 |
| Duplicate entity groups | 0 | 0 |
| Unresolved decisions | 8 | 10 |
| False sector/product/ambiguous acceptances | 0 | 0 |
| New companies | 9 | 4 |
| Embedding requests | 0 | 23 |

Both began with empty isolated PostgreSQL ledgers, processed the same order, and waited for Exa enrichment before the next mention. The model, resolver prompt, source requirements and cache were shared. Exact identifier/name retrieval is combined with the top five fuzzy candidates; hybrid adds the top five cosine candidates. Similarity only proposes candidates; the LLM decides identity. No additional database service was introduced.

The test uses 12 real transcript mentions and 12 explicitly authored controls. Expected answers are kept outside model inputs. Engineering pilots informed the guardrails before this final comparison, so this is a development benchmark, not held-out accuracy. Parent/subsidiary, corporate rename, same-name businesses, products, sectors and ambiguous names are represented. Neither method is validated at production scale.

Hybrid incorrectly merged Costco into BranchOut, Alphabet into Walmart, and Mercury fintech into Google. These were decision failures after candidate retrieval, not evidence that embeddings are inherently unsuitable. Broader recall exposed unrelated candidates to an unreliable adjudicator. Both retrieved the correct company in the two eligible alias matches; the small denominator excludes earlier unresolved identities.

| Mention | Expected | Option 2 | Option 3 |
| --- | --- | --- | --- |
| BranchOut Food | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Nasdaq | NOT_COMPANY | UNRESOLVED | UNRESOLVED |
| natural food space | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| snack food industry | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Costco | NEW_COMPANY | NEW_COMPANY | MATCH |
| Walmart | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Microdryd | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Crispy Greens | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| BranchOut | MATCH | MATCH | MATCH |
| N-Wave | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Starbucks | NEW_COMPANY | NEW_COMPANY | UNRESOLVED |
| MicroDry | MATCH | UNRESOLVED | UNRESOLVED |
| Alphabet Inc. | NEW_COMPANY | NEW_COMPANY | MATCH |
| Google LLC | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| Google Chrome | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Mercury | NEW_COMPANY | NEW_COMPANY | MATCH |
| Mercury | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Mercury | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Meta Platforms | NEW_COMPANY | UNRESOLVED | UNRESOLVED |
| Facebook | MATCH | NEW_COMPANY | UNRESOLVED |
| Crispy Fruit | NOT_COMPANY | NOT_COMPANY | NOT_COMPANY |
| Branch Out Food | MATCH | MATCH | MATCH |
| Sow Good Inc. | NEW_COMPANY | NEW_COMPANY | NEW_COMPANY |
| the supplier | UNRESOLVED | UNRESOLVED | UNRESOLVED |

## Fresh full transcript run

Run `111922e0-0d1b-42ec-9f2e-50ce13fe5394` completed from an empty public ledger: **5 companies, 15 claims, 37 evidence rows, 53 sources** (52 web sources plus the podcast). Companies: BranchOut Food, Walmart, MicroDried, Costco and Starbucks. No sector rows or duplicate companies were present. N-Wave, Nasdaq and Peru were withheld as unresolved.

This fresh extraction resolved Microdryd to MicroDried; the fixed comparison withheld Microdryd/MicroDry. Different extracted context and live research changed the outcome. The fresh run did not extract the BranchOut/MicroDry alias variants, so alias success comes from the fixed comparison, not this full run.

The previous episode run had 24 accepted claims and 78 evidence rows. The new 15/37 totals reflect a new extraction and stricter identity filtering; they do not establish higher recall or precision. The prior complete database is retained in `artifacts/backups/before-resolution-comparison.dump`, with a baseline JSON alongside it.

## Remaining limits

- Enrichment is source-backed model output, not human verification. Starbucks received `starbucks.com.sg`, a regional domain; several domains remain unknown. Some descriptions go beyond the single cited passage. Geography and funding-stage vocabularies also need stricter review. Do not treat profile completeness as correctness.
- The gate excludes brands/products/divisions rather than inferring their owner. Separately identifiable subsidiaries remain distinct. Shared domains alone do not authorize a merge.
- Unresolved companies and affected claims stay in durable run artifacts. PostgreSQL stores accepted identities, aliases, evidence and decisions; LangSmith is operational debugging, not the only provenance store.
- Provider responses are real and cached, not canned fixtures. Shared caching makes observed wall times unsuitable for speed comparison. Hybrid's lower research cost partly reflects incorrect merges skipping enrichment.
- Retrieval currently scans the ledger. Move lexical lookup to indexed Postgres queries before scaling; retain embeddings only if a larger reviewed benchmark shows a benefit.
- Claim entailment still needs review: “got our dragon fruit product in front of Starbucks” was strengthened into “secured product placement.” Identity matching does not fix this extraction error.
- Global resolution spending limits, full crash-boundary testing and concurrent identity creation need further hardening before multi-worker use.

## Verification and artifacts

Raw comparison files: `artifacts/matching-v3-{lexical,hybrid,summary}.json`. Test cases: `evaluation/cases.jsonl`. Public data is independent of the experiment schemas visible in pgAdmin. The fresh hosted LangSmith root was read back with an end time and no error.

Next: review disputed identities and enrichment fields, then expand to human-reviewed episodes before changing candidate retrieval. Keep option 2 as the default until that evidence supports replacing it.

Final checks: 28 tests passed, no Alembic schema drift, Ruff checks passed and the React production build succeeded. The local viewer was inspected with the five committed companies and their claims. A post-comparison write-boundary guard rejects canonical-key collisions unless replaying the exact saved mention; it did not affect these single-worker results.
