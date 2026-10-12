# Six-table schema

Null means unknown. All IDs are UUIDs. JSONB replaces intermediate tables, not durable evidence.

## runs

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| status | TEXT | no |
| input | JSONB | no |
| operation_key | TEXT | no |
| progress | JSONB | no |
| result | JSONB | yes |
| cost | NUMERIC(14, 6) | yes |
| trace_id | UUID | yes |
| trace_url | TEXT | yes |
| trace_status | TEXT | no |
| error | TEXT | yes |
| created_at | TIMESTAMP WITH TIME ZONE | no |
| finished_at | TIMESTAMP WITH TIME ZONE | yes |

## companies

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| name | TEXT | no |
| domain | TEXT | yes |
| linkedin_url | TEXT | yes |
| sector_id | TEXT | yes |
| subsector_id | TEXT | yes |
| description | TEXT | yes |
| ownership_status | TEXT | yes |
| funding_stage | TEXT | yes |
| capabilities | TEXT[] | yes |
| end_markets | TEXT[] | yes |
| headquarters_country_codes | TEXT[] | yes |
| operating_country_codes | TEXT[] | yes |
| operating_region_codes | TEXT[] | yes |
| industry_codes | JSONB | yes |
| financial_observations | JSONB | yes |
| identity | JSONB | no |
| field_evidence | JSONB | no |
| created_at | TIMESTAMP WITH TIME ZONE | no |

## people

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| name | TEXT | no |
| linkedin_url | TEXT | yes |
| identity | JSONB | no |
| created_at | TIMESTAMP WITH TIME ZONE | no |

## sources

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| kind | TEXT | no |
| provider | TEXT | no |
| external_id | TEXT | no |
| title | TEXT | no |
| url | TEXT | yes |
| published_at | TIMESTAMP WITH TIME ZONE | yes |
| retrieved_at | TIMESTAMP WITH TIME ZONE | no |
| content | JSONB | no |
| metadata | JSONB | no |
| content_hash | TEXT | no |
| version_hash | TEXT | no |
| raw_artifact | JSONB | yes |
| run_id | UUID | no |
| created_at | TIMESTAMP WITH TIME ZONE | no |

## claims

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| text | TEXT | no |
| participants | JSONB | no |
| speaker_person_id | UUID | yes |
| status | TEXT | no |
| extraction | JSONB | no |
| annotation | JSONB | yes |
| run_id | UUID | no |
| created_at | TIMESTAMP WITH TIME ZONE | no |

## evidence

| Property | PostgreSQL type | Nullable |
| --- | --- | --- |
| id | UUID | no |
| claim_id | UUID | no |
| source_id | UUID | no |
| locators | JSONB | no |
| quote | TEXT | no |
| speaker_label | TEXT | yes |
| role | TEXT | no |

## JSON contracts

`sources.content` holds normalization version, provider ID, coverage, timing status and stable segments (text, seconds, native speaker and optional words). `raw_artifact` stores filename and SHA-256. Source metadata and source versions remain immutable.

`claims.participants` contains kind, entity ID, name and subject/object/mentioned role. `speaker_person_id` stays null without identity evidence. `extraction` holds model/prompt/run provenance and attribution uncertainty; `annotation` holds forward-looking classification, evidence segment IDs and rationale.

`evidence.locators` contains segment ID and exact character offsets. Every quote points to its source version.

`companies.identity` holds the final identity outcome and evidence, including migrated old decisions. `field_evidence` links profile fields to support. `financial_observations` has typed amount, currency, date (unknown allowed), basis, source and quote; valuation, funding_raised and acquisition_price are separate types.

`runs.progress` contains operation state and immutable artifact references. Raw candidates/rejections live in artifacts; durable claims and final identity decisions live in PostgreSQL. LangSmith is supplementary.

## Inspect in pgAdmin

Open Query Tool on the yoyo database:

```sql
SELECT c.name, cl.text, cl.annotation->>'time_class' AS time_class,
       e.quote, e.speaker_label, e.locators
FROM companies c
JOIN claims cl ON cl.participants @> jsonb_build_array(jsonb_build_object('id', c.id::text))
JOIN evidence e ON e.claim_id = cl.id;
```

Migration 0002 backfills and verifies IDs, evidence quotes and segment counts in a staging schema before retiring passages, proposals and identity_decisions in one transaction. The pre-migration database backup remains in ignored artifacts/backups/.
