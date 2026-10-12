# Reuse and boundaries

- `yoyo/transcripts/ttml.py`: adapted pure `parse_ttml`, `_parse_time` and `_join_words` from `type/human_data/api/transcription/apple_local.py`, used by FYE's podcast benchmark. Preserves Apple word/segment times and native speaker labels. Removed its provider/network wrapper.
- `transcripts/normalize.py` and `transcripts/models.py`: typed, provider-neutral seconds and stable source-version segment IDs; adapted validation ideas from `human_data/operations/validation.py`, adding finite values, empty-word safety and explicit missing timing.
- FYE `podcast_tech.md`, `apple/common.py`, `apple/search.py`, `apple/metadata.py`, and benchmark retrieval scripts were inspected. Retrieval/authentication are not copied into this extraction milestone. The CLI accepts actual saved provider output.
- Metaspark sentence normalizers informed field mapping; unchecked word indexing and first-speaker assumptions were not carried over.
- Metaspark `scripts/trending_insights/ideas.py` informed structured output plus verbatim quote prompting. Its ranking, top-k filtering, Firestore and editorial schema are not needed here.
- No existing generic raw-claim/classification module was found in those folders. `claim_models.py`, `grounding.py`, `validate.py`, `model.py` and `pipeline.py` implement that boundary directly. Classification is a separate model operation, persisted on the claim.
- FYE OpenAI/Exa/Parallel credentials were copied into ignored `.env` with authorization; only OpenAI was used. No matching Jev credential was needed.

No source repo was modified. No transcript archive or credentials are committed.
