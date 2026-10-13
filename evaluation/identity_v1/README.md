# Identity regression set v1

Frozen 24-case development set for the “Mention | Expected | Previous | New with metadata” comparison. Twelve actual episode mentions plus twelve authored controls. Expected decisions are provisional, not human-reviewed truth. In particular, review the Crispy Greens brand/company policy before changing its label.

- `cases.jsonl`: ordered IDs, source provenance, identity packets including episode metadata, original inputs, group labels and expected outcomes.
- `baseline.jsonl`: immutable prior/new outcomes and selected company IDs; repeated Mercury mentions remain distinct through case IDs.
- `manifest.json`: versions, hashes, model, provenance and limitations.

## Run

From the repository root, with configured provider keys:

```sh
uv run python -m evaluation.compare evaluation/identity_v1/cases.jsonl --label YOUR_FRESH_LABEL --mode lexical
uv run python -m evaluation.identity_v1.score artifacts/YOUR_FRESH_LABEL-lexical.json
```

The comparison runner passes only `mention` to the resolver. Labels, previous outcomes and expected answers never enter model inputs. Run cases in order against an empty ledger. Claims of matching accuracy must distinguish errors caused by a missing earlier entity from errors against an available candidate. The scorer also reports merges, duplicates, abstentions and scope violations.

To reproduce the old input format, use each case's `previous_mention` with the old implementation commit in the manifest. Exact historical responses live only in ignored local artifacts; no canned provider outputs are used as runtime answers.

Keep this version immutable. Record human adjudication or policy changes in a new version with reasons; do not silently alter labels to improve a score. Add new episodes as a separate held-out set before further tuning.
