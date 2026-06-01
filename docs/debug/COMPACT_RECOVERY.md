# Compact Recovery

Updated: 2026-06-01 19:21 +07

## Current Task
CONTINUOUS-SCRAPE-001 complete.

## Current Branch
agent-run

## Latest Root Implementation Commit
f26b208

Note: realtime scrape quality gate is committed in `f236820`; realtime evidence is committed in `b87238c`; continuous scraping implementation/evidence is committed in `f26b208`. This recovery file is maintained in the follow-up docs/evidence state commit, so use `git log --oneline -5` for the current top commit.

## Active Phase
Continuous realtime scraping worker and harness complete; docs/evidence state update in progress.

## Completion Summary
- Runtime sample/fallback jobs were removed from scraper and pipeline user-facing refresh paths; `/sample` now returns 410 and pipeline skip/fallback paths do not fabricate sample catalog jobs.
- Existing Docker job rows were purged and reloaded through the real scraper/pipeline path. Current runtime has `10` jobs, all real-source rows, all rich descriptions over 200 characters, and all with extracted skills.
- Rich job-description storage/API/UI now supports `raw_description_html`, `description_text`, `description_sections`, responsibilities, requirements, nice-to-have, benefits, metadata, required/preferred/extracted skills, and source fields where available.
- Skill autocomplete now uses `8888` taxonomy entries from O*NET 30.3 plus local Indonesian/technical aliases. API checks for `s`, `machine`, and `data` return multiple realistic suggestions.
- The blue custom cursor ring/dot was removed from the product UI surface; theme toggle state was stabilized in the nested frontend app.
- Product-quality Selenium audit passed: `48/48` semantic checks across jobs, recommendations, theme toggle, skills autocomplete, and five real job detail pages.
- Frontend validation passed: `npm run lint` with existing warnings only and `npm run build`.
- Backend focused validation passed: job description parser, skill taxonomy search, full-pipeline sample-fallback guard, and red-team fallback guard tests.
- Realtime scraper follow-up found `/scrape/run` could still return Glints listing summaries or empty descriptions. Fixed with source priority, bounded realtime URL/concurrency caps, a minimum description/skill-signal quality gate, and richer inline heading parsing.
- Current direct realtime scraper evidence: `/scrape/run?limit=10` returned 7 Kalibrr jobs, all 476-2655 description characters, all with source URLs and skill signals; quality gate rejected 11 bad candidates.
- Current DB/API evidence after purge and `refresh_jobs=true`: 7 Kalibrr jobs, `sample_jobs=0`, `under_300_desc=0`, `no_skill_signal=0`.
- Continuous scraping architecture decision: keep `/scrape/run` and `/pipeline/run refresh_jobs=true` finite, and run indefinite scraping through a separate `scraper-worker` process under the Docker Compose `continuous` profile.
- Continuous worker module: `services.pipeline.continuous_scraper`.
- Bounded harness scripts: `scripts/harness_continuous_scrape.py` and `scripts/check_realtime_job_quality.py`.
- Continuous metadata migration: `015_continuous_scrape_metadata`; running Docker PostgreSQL was verified at revision `015_continuous_scrape_metadata`.
- Stable upsert identity now prefers normalized `source_url` and uses `ON CONFLICT (source_url)` for non-empty URLs, preventing duplicate explosions across cycles.
- Bounded Docker harness evidence:
  - 1 cycle: DB total `7 -> 8`, quality guard passed, API total matched DB.
  - 2 cycles: DB total stayed `8` across both cycles, inserted estimate `0` per cycle, quality guard passed after each cycle.
- Pipeline `refresh_jobs=true` remains compatible and returned 200 with `ranked=8`, `total_candidates=8`, and `scraper_run+database:upserted=8`.
- Final DB/API guard: 8 Kalibrr jobs, 8 distinct source URLs, descriptions 476-2655 chars, `sample_jobs=0`, `under_min_description=0`, `no_skill_signal=0`, `missing_source_url=0`, API total equals DB total.
- Pre-existing unrelated dirty/untracked work remains present and must not be staged.

## Next Action
Commit this scoped debug/agent state update, then stop. Next unfinished phase is larger-source scraper coverage/reliability hardening or broader ML/security runtime probes if explicitly requested.
