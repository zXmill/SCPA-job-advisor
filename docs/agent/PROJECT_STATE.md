# Project State

Updated: 2026-05-25 20:22 +07

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
- ML: `MODEL_NAME`, `MODEL_DIR`, `SBERT_ENABLE_TRANSFORMER`, `SBERT_FORCE_FALLBACK`, `EMBEDDING_CACHE_TTL`, `DQN_*`, `CONTINUAL_TRAINING_*`.

## Ports
- Frontend: 3000 when run by Next.js.
- Gateway: 8000.
- Scraper: 8001.
- SBERT: 8002.
- NCF: 8003.
- DQN: 8004.
- Pipeline: 8005.
- PostgreSQL: 5432.

Current `docker-compose.yml` publishes PostgreSQL, gateway, scraper, SBERT, NCF, DQN, and pipeline to host ports. Later security work should restrict internal services.

## Database And Migrations
- Alembic config: `alembic.ini`, script location `db/alembic`, version locations `db/migrations`.
- Detected migration files: `001_initial_schema.py` through `008_feature_extension_foundation.py`.
- Duplicate/legacy Alembic version folder exists at `db/alembic/versions/004_add_company_logo.py`.
- DB validation has not been rerun in this initializer. The reference report says `alembic heads` returned `008_feature_extension_foundation (head)` on 2026-05-25.

## ML Model Inventory
- SBERT: multilingual SentenceTransformer default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; local fine-tuned artifact files exist under ignored `services/sbert/weights/fine_tuned_jupyter/`.
- NCF: online NCF/NeuMF service with JSON and `.pt` artifacts under ignored `services/ncf/weights/` and report artifacts.
- DQN: online DQN service with replay/policy artifacts under ignored `services/dqn/weights/` and report artifacts.
- Evaluation and smoke artifacts exist under `reports/` and `notebooks/training_runs/`.

## Known Working Areas
- Repository contains extensive pytest coverage and local report evidence of backend health.
- Reference report records `.venv\Scripts\python.exe -m pytest -q` as `291 passed, 11 warnings` on 2026-05-25. This has not been rerun during this initializer.
- Route, model, migration, and test surfaces are discoverable from current files.

## Known Broken Areas
- Frontend lint still reports warnings, but the blocking hook-order error in `frontend/src/app/recommendations/page.tsx` has been fixed and validated locally.
- Internal Docker services are exposed to host ports.
- Scraper `/scrape/url` accepts arbitrary URLs and needs SSRF protection.
- Gateway `/pipeline/run` is unauthenticated and bypasses protected recommendation/profile handling.
- CI runs a selected pytest subset and does not currently gate frontend lint/build.
- JWT/CORS defaults are too permissive outside Compose.
- Feedback forwarding can report queued without a durable retry outbox.
- No fresh import validation was run during this initializer, so known broken imports remain unknown.

## Current Blockers
- Dirty git state existed before this initializer: `README.md` modified and many project files untracked. Do not stage unrelated files.
- Most live project files remain untracked in git. Cleanup must not treat untracked files as unused.
- `frontend/` is a nested Git repository. Frontend code fixes must be committed inside `frontend/` as well as recorded in root `docs/agent/`.

## Last Completed Task
`P0-FE-001` - frontend hook-order violation fixed in nested frontend commit `6e76e92` and validated with lint/build.

## Next Task
Return to `P0-002`: rerun safe-cleanup validation after the frontend hook-fix commit.
