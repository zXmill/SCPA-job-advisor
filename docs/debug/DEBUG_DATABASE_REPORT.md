# Debug Database Report

Updated: 2026-06-01 19:21 +07

Status: running Docker PostgreSQL schema reconciled and product-quality rich job/skill schema applied through `014_rich_job_desc_skill_sources`.

## Required Checks
- Alembic heads.
- Migration apply status when a database is available.
- ORM/schema alignment.
- Important tables and relationships.
- Recommendation, feedback, skills, and job-required-skill query paths.
- Index coverage for hot paths.

## Baseline Results
- Local Alembic head command passed: `012_ab_testing_and_monitoring (head)`.
- Existing postgres container responds to `pg_isready`.
- Live database initially reported `001_initial_schema`.
- `alembic upgrade head` applied migrations through `012_ab_testing_and_monitoring`.
- `alembic current` now reports `012_ab_testing_and_monitoring (head)`.
- Full pytest, including `db/tests/test_models.py` and `db/tests/test_seed_contracts.py`, passed.
- API runtime probe reconciliation later found the running Docker PostgreSQL database at `011_job_alerts`, with `experiments`, `experiment_assignments`, and `experiment_metrics` absent.
- Applied the existing `012_ab_testing_and_monitoring` table/index DDL via `docker compose exec -T postgres psql` because the gateway image does not include Alembic and Postgres is not host-exposed.
- Post-repair checks now return `012_ab_testing_and_monitoring`, `experiments`, `experiment_assignments`, and `experiment_metrics`.

## Open Validation
- Container-local Alembic is still not part of the gateway runtime image by design. Future migration validation should explicitly target the Docker PostgreSQL database instead of assuming host Alembic and compose DB are the same target.

## Feedback/Slate Relationship Finding
- The `feedback_events.slate_id` FK correctly rejects feedback for unknown served slates.
- Browser evidence showed the gateway violated the application-side contract by returning an unpersisted slate ID.
- Current-source regression verifies `/api/recommendations` now creates the `served_slates` row before `/api/recommendations/feedback` writes `feedback_events`.
- Test cleanup now truncates `feedback_events`, `served_slate_items`, and `served_slates` to keep DB tests isolated.

## Code Review Remediation Migration Finding
- R-2 is fixed. `009_reco_hot_indexes.py` now creates/drops hot indexes with PostgreSQL concurrent DDL inside Alembic `autocommit_block()`, so fresh deployments do not create these indexes with long write-blocking index builds.
- `013_hot_indexes_concurrent.py` is retained as an idempotent repair migration for databases already at `012`; it now uses `autocommit_block()` correctly and does not drop 009-owned indexes on downgrade.
- Validation passed: `upgrade head`, `downgrade 012_ab_testing_and_monitoring`, `upgrade head`, `current`, and `heads`.

## Runtime Contract Pass Database Impact
- No database schema or migration changes were made during the runtime-contract pass.
- The final fixes were frontend request-state handling and gateway CORS configuration only.
- Runtime audit evidence used the existing running Docker PostgreSQL state; no new migration validation was required for this bounded phase.

## Product Quality Schema/Data Update
- Updated: 2026-06-01 05:15 +07.
- Root commit: `fccb8a4 feat: require real job data with rich descriptions and skill taxonomy`.
- New migration: `014_rich_job_desc_skill_sources`.
- Job storage now supports rich description and data-signal fields: raw HTML, full text, parsed sections, responsibilities, requirements, nice-to-have, benefits, seniority, employment type, job function, industry, education/experience fields, required/preferred/extracted skills, source URL, and source update timestamp.
- Current Docker PostgreSQL state after purge/rescrape:
  - `jobs=10`
  - `rich_jobs=10`
  - `jobs_with_extracted_skills=10`
  - `real_source_jobs=10`
  - `skills=8888`
  - `alembic_version=014_rich_job_desc_skill_sources`
- Existing shallow/sample-like job rows were removed before the real-source refresh. The runtime catalog currently contains only real-source rows.
- Remaining database limitation: the real-source refresh is intentionally bounded to 10 jobs for this phase; larger real scrape batches need a separate reliability pass.

## Realtime Scrape Quality Refresh: 2026-06-01
- After fixing the realtime quality gate, local job-derived runtime tables were purged and the pipeline was run with `refresh_jobs=true`.
- Final Docker PostgreSQL quality state:
  - `source=kalibrr`
  - `jobs=7`
  - `min_desc=476`
  - `avg_desc=1334.9`
  - `max_desc=2655`
  - `with_source_url=7`
  - `with_skill_signal=7`
  - `sample_jobs=0`
  - `under_300_desc=0`
  - `no_skill_signal=0`
- The current product catalog therefore contains only real-source, quality-gated rows.

## Continuous Scrape Metadata and Idempotent Upsert
- Updated: 2026-06-01 19:21 +07.
- New migration: `015_continuous_scrape_metadata`.
- New `jobs` lifecycle metadata fields: `external_id`, `scraped_at`, `first_seen_at`, `last_seen_at`, `quality_status`, `quality_reject_reason`, and `content_hash`.
- Upsert identity now prefers normalized `source_url`; non-empty `source_url` has a partial unique index and is used as the conflict target for repeated realtime cycles.
- Migration deactivates duplicate legacy rows with the same non-empty `source_url` before adding the uniqueness contract, then creates/drops the partial unique index concurrently to reduce deploy lock risk.
- `first_seen_at` is preserved on conflict; `last_seen_at`, `scraped_at`, `content_hash`, and rich job payload fields update when the source is seen again.
- Host Alembic validation: `heads` and `current` both reported `015_continuous_scrape_metadata (head)`.
- Running Docker PostgreSQL was repaired/verified at `015_continuous_scrape_metadata`; all continuous metadata columns are present.
- Repeated bounded worker evidence:
  - 1 cycle: DB total `7 -> 8`, inserted estimate `1`, duplicate/update estimate `7`.
  - 2 cycles: DB total stayed `8` in both cycles, inserted estimate `0` each cycle, duplicate/update estimate `8` each cycle.
- Final database guard: `source=kalibrr`, `jobs=8`, `distinct_source_urls=8`, `min_desc=476`, `avg_desc=1398.4`, `max_desc=2655`, `with_source_url=8`, `with_skill_signal=8`.
- Quality guard remains clean: `sample_jobs=0`, `under_min_description=0`, `no_skill_signal=0`, `missing_source_url=0`, and app API total matches DB total.
