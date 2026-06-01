# Compact Recovery

Updated: 2026-06-01 09:05 +07

## Current Task
DATA-QUALITY-PRODUCT-UI-001 complete with realtime scraper quality follow-up.

## Current Branch
agent-run

## Latest Root Commit
f236820

Note: product/data changes are committed in root commit `fccb8a4`; the product-quality audit harness is committed in `7286d84`; nested frontend app state is committed in `frontend/` commit `999e2a8`; realtime scraper quality gate follow-up is committed in `f236820`.

## Active Phase
Final evidence/report update for the data-quality and product UI remediation pass.

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
- Pre-existing unrelated dirty/untracked work remains present and must not be staged.

## Next Action
After the scoped final documentation/evidence commit, stop. Next unfinished phase is a separate broader ML runtime smoke/security probe or larger-source scraper coverage/reliability hardening if requested.
