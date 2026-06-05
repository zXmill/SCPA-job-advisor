# Continuous Realtime Scraping Evidence

Updated: 2026-06-01 19:15 +07

## Audit Summary

Finite assumptions found:

- `POST /scrape/run?limit=10` was a bounded one-shot scrape endpoint.
- `POST /pipeline/run` with `refresh_jobs=true` triggered one scrape/upsert cycle.
- The prior upsert identity was derived from scraper job id/content hash, which could differ from a stable source URL.
- The `jobs` table had rich description and source fields, but lacked continuous scrape lifecycle fields such as `first_seen_at`, `last_seen_at`, `scraped_at`, `quality_status`, and `content_hash`.

Architecture decision:

- Keep request handlers finite.
- Add a separate `scraper-worker` process for continuous mode.
- Use `limit` only as a per-cycle bound.
- Keep PostgreSQL `jobs` as the app source of truth.
- Keep Kalibrr as the allowed production-quality realtime source.

## Tests

```text
.\.venv\Scripts\python.exe -m pytest tests\test_continuous_scraper.py tests\test_job_upsert_idempotency.py -q
5 passed, 1 warning
```

```text
.\.venv\Scripts\python.exe -m pytest db\tests\test_models.py::TestJobColumns::test_job_has_required_columns db\tests\test_models.py::TestIndexes::test_jobs_indexes tests\test_pipeline_contracts.py tests\test_pipeline_telemetry.py -q
5 passed, 1 warning
```

```text
.\.venv\Scripts\python.exe -m pytest tests\test_job_description_quality.py tests\test_red_team_failure_modes.py::test_scraper_normalizes_kalibrr_indonesia_next_payload_with_logo -q
8 passed, 1 warning
```

## Migration and Docker

```text
.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads
015_continuous_scrape_metadata (head)
```

```text
docker compose config --quiet
pass
```

```text
docker compose --profile continuous config --quiet
pass
```

The running Docker PostgreSQL database was verified at:

```text
015_continuous_scrape_metadata
```

Continuous metadata columns present:

```text
content_hash
external_id
first_seen_at
last_seen_at
quality_reject_reason
quality_status
scraped_at
```

## One-Shot Scrape

Command:

```text
docker compose exec -T scraper python -c "... POST http://127.0.0.1:8001/scrape/run?limit=10 ..."
```

Result:

```json
{
  "count": 8,
  "deduplicated": 149,
  "min_desc": 476,
  "max_desc": 2655,
  "sources": ["kalibrr"],
  "quality_gate": {
    "count": 8,
    "rejected": 11,
    "rejection_reasons": {
      "missing_skill_signal": 7,
      "short_description": 4
    },
    "min_description_chars": 300
  }
}
```

## Bounded Continuous Harness

Artifacts:

```text
reports/debug/continuous_scrape/bounded_1/
reports/debug/continuous_scrape/bounded_2/
```

One-cycle bounded run:

```text
cycles=1
accepted_jobs=8
rejected_jobs=11
db_total_before=7
db_total_after=8
estimated_inserted_jobs=1
estimated_updated_or_duplicate_jobs=7
quality_guard passed
app_api_total=8
app_api_db_total_mismatch=false
```

Two-cycle bounded run:

```text
cycles=2
cycle 1: db_total_before=8, db_total_after=8, inserted=0, updated_or_duplicate=8
cycle 2: db_total_before=8, db_total_after=8, inserted=0, updated_or_duplicate=8
quality_guard passed after each cycle
app_api_total=8
app_api_db_total_mismatch=false
```

This proves repeated cycles do not create duplicate explosions for the current source set.

## Pipeline Refresh Compatibility

Command:

```text
docker compose exec -T pipeline ... POST http://127.0.0.1:8005/pipeline/run refresh_jobs=true
```

Result:

```json
{
  "status": 200,
  "ranked": 8,
  "total_candidates": 8,
  "scrape": {
    "source": "scraper_run+database:upserted=8",
    "scraped_jobs": 8,
    "upserted_jobs": 8,
    "returned_jobs": 8,
    "quality_gate": {
      "accepted": 8,
      "rejected": 11,
      "rejection_reasons": {
        "missing_skill_signal": 7,
        "short_description": 4
      }
    }
  }
}
```

## Final DB/API Guard

DB summary:

```text
source=kalibrr
jobs=8
distinct_source_urls=8
min_desc=476
avg_desc=1398.4
max_desc=2655
with_source_url=8
with_skill_signal=8
```

Quality guard:

```json
{
  "total_jobs": 8,
  "sources": {"kalibrr": 8},
  "sample_jobs": 0,
  "under_min_description": 0,
  "no_skill_signal": 0,
  "missing_source_url": 0,
  "generic_listing_descriptions": 0,
  "disallowed_sources": {},
  "app_api_total": 8,
  "app_api_db_total_mismatch": false
}
```

Gateway:

```text
GET http://localhost:9000/health -> healthy
GET http://localhost:9000/ready -> ready
GET http://localhost:9000/api/jobs?page=1&limit=10 -> total=8, DB-backed Kalibrr jobs
```

## Secret Scan

Command:

```text
rg -n "<redacted secret-patterns>" reports\debug\continuous_scrape scripts\harness_continuous_scrape.py scripts\check_realtime_job_quality.py services\pipeline\continuous_scraper.py
```

Result: no matches.

## Known Limitations

- The current production-quality source evidence is Kalibrr only.
- The worker reports inserted count exactly as DB total growth and reports repeated-cycle updates as `estimated_updated_or_duplicate_jobs`.
- No LinkedIn production scraping was added.
- The host-side guard script can point to the wrong local database if the app PostgreSQL is only reachable from Docker; the Docker worker/module guard is the accepted runtime evidence path.
