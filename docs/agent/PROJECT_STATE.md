# Project State

Updated: 2026-05-25 23:59 +07

## Architecture Summary
SCPA is a full-stack career recommendation platform. The public path is a Next.js frontend calling a FastAPI gateway. The gateway assembles user/profile/job data and forwards recommendation work to an internal pipeline. The pipeline orchestrates scraper candidates, SBERT semantic scoring, NCF/NeuMF affinity scoring, DQN career-action/rerank signals, and final aggregation.

## Services Detected
- `frontend/`: Next.js 16, React 19, TypeScript, Tailwind v4.
- `services/gateway/`: FastAPI public API and auth boundary.
- `services/pipeline/`: FastAPI orchestration service with scrape, encode, NCF, DQN, aggregate, feedback, and invalidate endpoints.
- `services/scraper/`: FastAPI scraper with HTML, URL, run, and sample endpoints.
- `services/sbert/`: FastAPI semantic embedding and matching service.
- `services/ncf/`: FastAPI online NCF/NeuMF service.
- `services/dqn/`: FastAPI online DQN service.
- `services/hybrid/`: FastAPI hybrid service not currently wired in `docker-compose.yml`.
- `db/`: SQLAlchemy models, Alembic environment, migration scripts, seed code, and DB tests.
- `tests/`: pytest coverage for auth, security, pipeline contracts, ML contracts, metrics, cache, fairness, edge cases, and sample flows.

## Entry Points
- Frontend dev: `frontend/package.json` script `dev`.
- Gateway ASGI app: `services.gateway.main:app`.
- Pipeline ASGI app: `services.pipeline.main:api`.
- Scraper ASGI app: `services.scraper.main:app`.
- SBERT ASGI app: `services.sbert.main:app`.
- NCF ASGI app: `services.ncf.main:app`.
- DQN ASGI app: `services.dqn.main:app`.
- Hybrid ASGI app: `services.hybrid.main:app`.
- Full stack: `docker-compose.yml`.

## Environment Variables
Key variables from `.env.example`, Docker Compose, and service code:
- Database: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `GATEWAY_DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`.
- Auth: `JWT_SECRET`, `JWT_REFRESH_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRY_HOURS`.
- Gateway/frontend: `PUBLIC_GATEWAY_URL`, `NEXT_PUBLIC_API_URL`, `PIPELINE_URL`, `HTTP_TIMEOUT_SECONDS`, `CORS_ALLOW_ORIGINS`, `CORS_ALLOWED_ORIGINS`.
- Pipeline/model URLs: `SCRAPER_URL`, `SBERT_URL`, `NCF_URL`, `DQN_URL`, `PIPELINE_USE_DB_CANDIDATES`, `PIPELINE_CANDIDATE_POOL_LIMIT`.
- Scraper: `SCRAPER_SEED_URLS`, `SCRAPER_INDONESIA_ONLY`, `SCRAPER_SAMPLE_ONLY`, `SCRAPER_MAX_URLS_PER_RUN`, `SCRAPER_CONCURRENCY`, source enable flags.
- ML: `MODEL_NAME`, `MODEL_DIR`, `SBERT_ENABLE_TRANSFORMER`, `SBERT_MODEL_LOADER`, `SBERT_MAX_SEQ_LENGTH`, `SBERT_FORCE_FALLBACK`, `EMBEDDING_CACHE_TTL`, `DQN_*`, `CONTINUAL_TRAINING_*`.

## Ports
- Frontend: 3000 when run by Next.js.
- Gateway: 8000.
- Scraper: 8001.
- SBERT: 8002.
- NCF: 8003.
- DQN: 8004.
- Pipeline: 8005.
- PostgreSQL: 5432.

Current `docker-compose.yml` publishes only the gateway on host port 8000. PostgreSQL, scraper, SBERT, NCF, DQN, and pipeline stay on the Docker network without host ports.

## Database And Migrations
- Alembic config: `alembic.ini`, script location `db/alembic`, version locations `db/migrations`.
- Detected migration files: `001_initial_schema.py` through `011_job_alerts.py`.
- Duplicate/legacy Alembic version folder exists at `db/alembic/versions/004_add_company_logo.py`.
- Current Alembic head after P3-FEAT-004-BE is `011_job_alerts`. Local upgrade, one-step downgrade to `010_feedback_outbox`, and re-upgrade passed on 2026-05-25.

## ML Model Inventory
- SBERT: active runtime loads the fine-tuned checkpoint at `models/sbert-indonesian-hybrid-manual-research/best` with `SBERT_MODEL_LOADER=transformers`, exposes `model_version=sbert-indonesian-hybrid-manual-research-best`, and keeps deterministic fallback only for explicit test/offline mode.
- NCF: online NCF/NeuMF service with JSON and `.pt` artifacts under ignored `services/ncf/weights/` and report artifacts.
- DQN: online skill-path DQN service with replay/policy artifacts under ignored `services/dqn/weights/` and report artifacts. It emits career milestone/skill actions and a compatibility rerank signal.
- Calibration: deterministic learned logistic calibrator in `services/pipeline/calibration.py` over static baseline, SBERT, NCF, DQN, skill gap, skill alignment, recency, salary, location, and interaction-depth features. Smoke evaluation is saved at `reports/ml/calibration_layer_smoke.json`.
- Evaluation and smoke artifacts exist under `reports/` and `notebooks/training_runs/`.

## Known Working Areas
- Repository contains extensive pytest coverage and local report evidence of backend health.
- JWT access and refresh signing secrets now fail fast when missing or shorter than 32 bytes in shared auth and gateway configuration.
- Gateway CORS origins now default to localhost in development and reject empty or wildcard origins in production.
- Gateway recommendation feedback now uses a durable database outbox with retry worker support for pipeline forwarding.
- DQN learning-path responses now expose an explicit MDP contract: state is user profile, missing skills, and market demand; actions are skill/course/certificate/career milestones; reward is skill-gap reduction plus job-match lift.
- Stage 5 aggregation now applies a learned logistic calibration layer while preserving `static_baseline_score` and ablation metadata.
- Gateway skill taxonomy autocomplete now supports excluding already-selected canonical skills and aliases.
- Frontend profile skill editing now uses backend skill taxonomy autocomplete and excludes selected skills.
- Gateway profile completeness summary is available at authenticated `GET /api/profile/completeness`.
- Frontend profile page now renders backend-computed profile completeness percent and item states.
- Gateway saved/skip job actions are available through authenticated save, unsave, skip, and saved-list endpoints backed by `user_job_interactions`.
- Frontend recommendation cards now expose save and skip actions backed by the saved/skip API, and skipped jobs are removed from the current recommendation slate.
- Frontend profile page now lists saved jobs from `GET /api/jobs/saved`.
- Gateway job alerts are available through authenticated create, list, update, and disable endpoints backed by the new `job_alerts` table.
- Frontend profile page now fetches job alerts, creates simple daily/weekly alerts, lists active alerts, and disables alerts through the backend API.
- Gateway job skill-gap detail endpoint now returns a page-ready contract with job context, required/matched/missing skills, explanation metadata, missing-job 404 behavior, and persisted `skill_gap_snapshots`.
- Frontend job detail page now renders skill-gap percent, required skills, matched skills, and missing skills from the backend contract.
- Gateway admin model-health endpoint is available at authenticated admin-only `GET /api/admin/model-health`; it summarizes pipeline status, downstream scraper/SBERT/NCF/DQN URLs, calibrator/aggregation stage status, telemetry, and continual-training state from pipeline health.
- Frontend analytics page now renders an admin-only model-health panel with pipeline status, model service status, stage p50/p95 telemetry, and continual-training state from `GET /api/admin/model-health`.
- Gateway recommendation responses now expose explicit `reason_filter_scores` and `reason_filter_labels` for semantic fit, interaction fit, career signal, location fit, and recency.
- Frontend recommendations page now supports sorting by reason filters (semantic fit, interaction fit, career signal, location fit, recency) in addition to match percent and recency. The active reason score is displayed in the card sidebar.
- Gateway authenticated `POST /api/profile/cv` endpoint accepts PDF and TXT uploads, extracts text, scans for known skills from the taxonomy, upserts matched skills into `user_skills`, and records `cv_uploaded_at`.
- Gateway authenticated `POST /api/profile/certificates` endpoint accepts PDF and image uploads, extracts text (PyPDF2 for PDFs, pytesseract for images when available), parses certificate name and issuer heuristically, looks up `certification_skills` for mapped skills, inserts `user_certifications` records, and upserts matched skills into `user_skills`.
- Gateway `POST /api/learning-path` now computes real-time market demand from `job_required_skills` counts, passes it to the DQN service, and returns it in the response. Each step includes its `market_demand` score when available.
- Gateway `GET /api/market-demand` endpoint returns top-N skills with demand scores and job counts derived from active job postings.
- Gateway `_resolve_target_role` now gracefully handles the missing `user_profiles` table (existing pre-migration schema gap).
- Latest local backend validation: `.\.venv\Scripts\python.exe -m pytest -q` passed with `348 passed, 1 warning` after P3-FEAT-007-BE.
- Latest frontend validation after P3-FEAT-007-FE: `npm run lint` passed with 16 existing warnings, `npm run build` passed.
- Latest backend validation after P5-ML-007: `.\.venv\Scripts\python.exe -m pytest -q` passed with `389 passed, 3 warnings`.
- Route, model, migration, and test surfaces are discoverable from current files.

## Known Broken Areas
- Frontend lint still reports warnings, but the blocking hook-order error in `frontend/src/app/recommendations/page.tsx` has been fixed and validated locally.
- Existing frontend lint warnings remain but do not fail lint.
- No fresh import validation was run during this initializer, so known broken imports remain unknown.

## Current Blockers
- Dirty git state existed before this initializer: `README.md` modified and many project files untracked. Do not stage unrelated files.
- Most live project files remain untracked in git. Cleanup must not treat untracked files as unused.
- `frontend/` is a nested Git repository. Frontend code fixes must be committed inside `frontend/` as well as recorded in root `docs/agent/`.

## Last Completed Task
`P5-ML-007` - Fine-tuned SBERT checkpoint runtime integration. Root commit pending.

## Next Task
Check TASK_QUEUE.json for next pending task.
