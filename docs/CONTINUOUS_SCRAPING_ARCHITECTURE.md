# Continuous Realtime Scraping Architecture

Updated: 2026-06-01 19:15 +07

## Decision

Continuous scraping is implemented as a separate worker process, not as an infinite HTTP request.

- Existing scraper API remains one-shot: `POST /scrape/run?limit=N`.
- Existing pipeline API remains one-shot: `POST /pipeline/run` with `refresh_jobs=true`.
- New worker module: `services.pipeline.continuous_scraper`.
- New Compose service: `scraper-worker` under profile `continuous`.
- App data source remains PostgreSQL table `jobs`.
- App API remains `GET /api/jobs?page=1&limit=10`.

The worker uses pipeline stage 1 directly. That keeps continuous scraping lightweight: it calls the scraper service, quality-gates results, and upserts jobs into PostgreSQL without running SBERT/NCF/DQN on every background scrape cycle.

## Continuous Mode

Run indefinitely:

```powershell
docker compose --profile continuous up -d scraper-worker
```

Stop:

```powershell
docker compose --profile continuous stop scraper-worker
```

The worker handles process shutdown through SIGINT/SIGTERM and exits cleanly after the current cycle.

## Bounded Harness Mode

Bounded runs use `SCRAPER_TEST_MAX_CYCLES` or `--test-max-cycles`; production mode must leave this unset.

```powershell
docker compose --profile continuous run --rm `
  -e SCRAPER_TEST_MAX_CYCLES=2 `
  -e SCRAPER_RUN_FOREVER=false `
  -e SCRAPER_CYCLE_INTERVAL_SECONDS=0 `
  scraper-worker `
  python -m services.pipeline.continuous_scraper `
  --test-max-cycles 2 `
  --cycle-interval-seconds 0 `
  --report-dir /app/reports/debug/continuous_scrape/bounded_2 `
  --api-base-url http://gateway:8000
```

## Configuration

- `SCRAPER_CONTINUOUS_ENABLED`: operator switch for continuous worker deployments.
- `SCRAPER_CYCLE_LIMIT`: per-cycle scrape/upsert bound, not a final target.
- `SCRAPER_CYCLE_INTERVAL_SECONDS`: normal sleep between cycles.
- `SCRAPER_MAX_EMPTY_CYCLES_BEFORE_BACKOFF`: empty-cycle threshold before backoff.
- `SCRAPER_BACKOFF_MIN_SECONDS`: minimum empty-cycle backoff.
- `SCRAPER_BACKOFF_MAX_SECONDS`: maximum empty-cycle backoff.
- `SCRAPER_ALLOWED_SOURCES`: allowed source set for quality guard, currently `kalibrr`.
- `SCRAPER_RUN_FOREVER`: production long-running behavior.
- `SCRAPER_TEST_MAX_CYCLES`: bounded harness/testing only.
- `SCRAPER_CYCLE_JITTER_SECONDS`: politeness jitter.
- `SCRAPER_QUALITY_MIN_DESC_CHARS`: quality gate minimum description length.

## Database Contract

Continuous upserts use normalized `source_url` as the conflict target. This prevents duplicate explosions across cycles and also handles legacy rows whose previous UUID was content-hash based.

The metadata migration deactivates duplicate legacy rows with the same non-empty `source_url` before creating the partial unique index. The source URL uniqueness index is created concurrently to reduce deploy-time write-lock risk.

New `jobs` metadata:

- `external_id`
- `scraped_at`
- `first_seen_at`
- `last_seen_at`
- `quality_status`
- `quality_reject_reason`
- `content_hash`

`first_seen_at` is preserved on update. `last_seen_at` and `scraped_at` advance on every accepted cycle. `content_hash` tracks mutable content changes separately from identity.

## Quality Gate

The continuous worker does not weaken the existing realtime gate. It still rejects:

- sample/fake jobs
- missing `source_url`
- descriptions under 300 characters
- generic listing descriptions
- jobs without required/preferred/extracted skill signal
- sources outside `SCRAPER_ALLOWED_SOURCES`

## Outputs

Artifacts are written under:

```text
reports/debug/continuous_scrape/
```

Each cycle emits:

- cycle number
- start/finish timestamps
- accepted jobs
- rejected jobs and grouped reasons
- upserted jobs
- estimated inserted count
- estimated updated/duplicate count
- source stats
- DB quality guard summary
- next sleep/backoff duration

## Source Policy

No LinkedIn production scraping was added. The current production-quality realtime data path remains Kalibrr. LinkedIn-like structure is a target schema behavior only, not a production scraping dependency.
