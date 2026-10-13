# One targeted identity fix

Changed only the target/counterparty pair-check instructions and target-relevant episode excerpts. The 24-case order, development examples and original expected labels remain visible. Frozen `identity_v1` is untouched. Raw live responses remain in ignored artifacts; this directory preserves inputs and results, not provider fixtures.

Original labels: 17/24 previously, 18/24 now; no observed incorrect merges or duplicate entities. Walmart now resolves; Crispy Greens moves from NEW_COMPANY to UNRESOLVED. Microdryd/MicroDry still converge. Nasdaq, N-Wave, Starbucks, Meta/Facebook and Crispy Greens remain review cases. This is a small development regression, not held-out accuracy.

## Proposed label adjudication (pending human review)

The original Crispy Greens NOT_COMPANY label is questionable: the official [Crispy Green story](https://crispygreen.com/pages/our-story) identifies the organization as a company, and its [product catalog](https://crispygreen.com/) identifies Crispy Fruit as the product line. In context, Crispy Greens may be a transcription variant of that company. Proposed target: company if the passage establishes that identity; otherwise unresolved. Do not silently relabel the old benchmark to raise its score.

A legal subsidiary is a separate company. A product or retail banner is not automatically a legal company. The new pilot flags Real Canadian Superstore/Loblaws and hospital versus health-system scope for review; these are not treated as confirmed correct labels.
