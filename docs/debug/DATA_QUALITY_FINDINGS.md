# Data Quality And Product UI Findings

Updated: 2026-06-01 02:34 +07

Status: active. Findings are confirmed from repository state, live API responses, live Docker PostgreSQL queries, and user-provided manual screenshots. Product code must not change until the relevant finding has evidence and a focused validation plan.

## Scope
- Frontend: `http://localhost:3000`
- Gateway: `http://localhost:9000`
- Local Docker PostgreSQL: `scpa-postgres-1`, database `db_scpa`
- Phase: job description depth, skill extraction context, skill autocomplete richness, sample-job removal, real-data scraping path, and the theme/cursor visual defect.

## BUG-DATA-JOB-DESCRIPTION-SHALLOW

Observed UI text:
- App job detail shows a one-line body such as `Data Scientist CBI Credit Bureau Indonesia South Jakarta...`
- User reference LinkedIn-style detail includes `Who We Are`, `Why Join Us`, `Role Overview`, `Job Responsibilities`, `Job Requirements`, `Nice to Have`, seniority, employment type, job function, and industry.

Affected route:
- `/jobs/{id}`

Expected behavior:
- Store and return full job detail text when legally and technically available.
- Preserve structured fields for sections, responsibilities, requirements, nice-to-have, benefits, seniority, employment type, job function, industry, and source metadata.
- Use the full detail text for SBERT, skill extraction, skill gap, and recommendation reasons.

Actual behavior:
- Live API returned shallow sample-like descriptions. Example `/api/jobs?page=1&limit=5` returned descriptions of roughly 130 to 180 characters.
- Live DB query showed `2614` of `2645` jobs have `length(description) < 200`.
- Current `jobs` schema has only `description`, `match_data`, and `skills_extracted_at` for job text and ML metadata.
- Current gateway `/api/jobs/{job_id}` selects only shallow fields and derives `source_url` and `skills` from `match_data`.

Evidence:
- Command: `Invoke-WebRequest http://localhost:9000/api/jobs?page=1&limit=5`
- Command: `docker compose exec -T postgres psql -U postgres -d db_scpa -c "select count(*) total_jobs, count(*) filter (where length(coalesce(description,'')) < 200) shallow_desc from jobs;"`
- Result: `total_jobs=2645`, `shallow_desc=2614`.
- Code: `services/scraper/main.py::_extract_linkedin_jobs` creates listing-card descriptions from `title company location`.
- Code: `services/pipeline/pipeline/normalizer.py` strips text into a single `description` field with no section parser.
- Code: `services/gateway/main.py::get_job` does not expose structured description fields.

Root-cause classification:
- Scraper listing-summary-only behavior.
- Storage/API contract lacks rich description fields.
- Pipeline normalizer does not parse or preserve detail sections.
- Frontend can only render the shallow `description` field it receives.

Pass condition:
- A real scraped job with an allowed source URL stores full `description_text` and structured sections.
- `/api/jobs/{id}` returns structured fields.
- Job detail page displays the structured sections when present and degrades cleanly when missing.

## BUG-DATA-SKILL-GAP-LOW-CONTEXT

Observed UI text:
- Screenshot shows skill gap `0%` and `0 of 1 required skills matched`, with only `Data` as the required skill.

Affected route:
- `/jobs/{id}` and `/api/jobs/{id}/skill-gap`

Expected behavior:
- Skill gap uses required, preferred, and extracted skills from the full job description.
- A Data Scientist role with the user-provided CBI-style description should extract skills such as Python, Linux, database design, REST APIs, Docker, Kubernetes, Airflow/Prefect, Git, MLOps, model versioning, model monitoring, credit scoring, and ML/DL algorithms.

Actual behavior:
- Current `services/gateway/main.py::_job_skill_gap` only reads `match_data.skills`.
- If upstream extraction produces one generic skill such as `Data`, the gap becomes low-context and misleading.

Evidence:
- Code: `_job_skill_gap` selects `title, company, match_data FROM jobs` and builds `required_skills` only from `match_data.get("skills", [])`.
- Live job rows store skill arrays in `match_data` but not required/preferred/extracted skill columns.

Root-cause classification:
- Skill gap depends on shallow upstream `match_data.skills`.
- No rich required/preferred skill contract exists yet.

Pass condition:
- Skill gap prefers `required_skill_names`, then `preferred_skill_names`, then `extracted_skill_names`, and falls back to `match_data.skills` only for legacy rows.

## BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE

Observed UI text:
- Typing `s` shows too few suggestions such as only `SQL`.
- Typing `Machine` and other common terms can show a loader or empty result.

Affected route:
- `/profile` skill editor and any onboarding skill editor.

Expected behavior:
- Search returns multiple real-world skills with category/source/confidence metadata.
- Queries such as `s`, `machine`, `data`, `python`, `docker`, `kubernetes`, `ml`, `ai`, `statistics`, `credit`, `airflow`, `terraform`, `english`, `komunikasi`, and `analisis` return relevant results.

Actual behavior:
- Live API `GET /api/skills/search?q=s&limit=20` returned only `SQL` and `English`.
- Live API `GET /api/skills/search?q=machine&limit=20` returned `[]`.
- Live API `GET /api/skills/search?q=data&limit=20` returned `[]`.
- Live DB query showed only `3` rows in `skills`: `English`, `Python`, and `SQL`.
- Current `services/pipeline/pipeline/extractors/skills.py` has a small hand list plus fake generated `Skill 001` to `Skill 429`.

Root-cause classification:
- Taxonomy is not a real skill dataset.
- Runtime DB was seeded with only a tiny subset.
- Search endpoint limits itself to existing rows and cannot return skills that are not seeded.

Pass condition:
- The runtime taxonomy is built from authorized real sources and local curated aliases.
- No fake `Skill 001` style generated taxonomy remains in production/runtime extraction.
- Focused tests prove common queries return realistic multi-suggestion results.

## BUG-DATA-SAMPLE-JOBS-IN-PROD

Observed behavior:
- User requires real job data only and explicitly forbids sample data.

Affected code paths:
- `services/scraper/main.py`
- `services/pipeline/stages/stage_1_scrape.py`
- `scripts/run_full_pipeline.py`
- `db/seed.py`

Expected behavior:
- Production/runtime job catalog should use real scraped or authorized API data only.
- If no real source is configured or scraping fails, runtime should return a controlled empty/degraded result, not silently seed or recommend local sample jobs.
- Local test fixtures may remain for tests only, but must not be used as runtime fallback.

Actual behavior:
- `services/scraper/main.py::scrape_run` returns `/sample` when no seed URLs are configured and again when all configured URLs return no unique jobs.
- `services/pipeline/stages/stage_1_scrape.py` returns `FALLBACK_JOBS` on scraper failure and returns fallback if the scraper yields no jobs.
- `scripts/run_full_pipeline.py` imports `scripts.sample_dataset`, fetches scraper `/sample`, merges `sample_jobs` into pipeline jobs, and uses sample data as the default pipeline dataset.
- Live `/api/jobs` returned sample-like companies and descriptions such as Tokopedia, Gojek, Grab Indonesia, OVO, and Google Indonesia with empty `source_url`.

Evidence:
- Live DB query: `missing_source_url=12`, sample-like rows have empty `source_url` and short descriptions.
- Code paths listed above directly call or return sample/fallback data.

Root-cause classification:
- Runtime sample fallback is mixed with production scraping and pipeline paths.

Pass condition:
- Runtime scraper/pipeline paths do not use sample jobs unless an explicit test-only flag is set.
- Local job purge script deletes existing job catalog and dependent job-state rows only after a real-data rescrape confirmation flag.
- Real-data rescrape inserts rows with non-empty `source_url`, full descriptions when available, and structured extracted skills.

## BUG-FE-CURSOR-RING-LOOKS-LIKE-LOADER

Observed UI:
- User screenshots show a blue circular indicator overlapping the theme toggle and skill input.
- User interpreted this as a stuck spinner/loading state.

Affected route:
- Global `AppLayout` on authenticated app pages.

Expected behavior:
- Theme toggle and skill input must not have a decorative overlay that looks like loading.
- Product UI should use familiar controls, especially in a career intelligence tool.

Actual behavior:
- `frontend/src/components/AppLayout.tsx` always renders `custom-cursor-dot` and `custom-cursor-ring`.
- `frontend/src/app/globals.css` sets `.custom-cursor-ring` to `position: fixed`, a blue ring border, and `z-index: 9998`.
- `.custom-cursor-hover .custom-cursor-ring` grows to `44px`, which matches the blue circles in the screenshots.

Root-cause classification:
- Isolated frontend UI affordance defect, not a theme-provider loading-state defect.

Pass condition:
- The decorative custom cursor is removed or disabled for product UI surfaces.
- Selenium screenshots show no blue ring overlay after hovering/clicking theme toggle and skill input.

## Next Exact Action
Implement scoped fixes in this order:
1. Remove or disable product-surface custom cursor overlay.
2. Remove runtime sample-job fallbacks and add a safe local purge/rescrape command path.
3. Add rich job-description storage/API/parser contract.
4. Replace fake/tiny skill taxonomy with an authorized real taxonomy baseline and Indonesian aliases.
5. Run focused backend/frontend tests, browser checks, and secret scan.
