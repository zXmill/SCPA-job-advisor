# Project State

Updated: 2026-05-25 21:05 +07

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

Current `docker-compose.yml` publishes only the gateway on host port 8000. PostgreSQL, scraper, SBERT, NCF, DQN, and pipeline stay on the Docker network without host ports.

## Database And Migrations
- Alembic config: `alembic.ini`, script location `db/alembic`, version locations `db/migrations`.
- Detected migration files: `001_initial_schema.py` through `009_reco_hot_indexes.py`.
- Duplicate/legacy Alembic version folder exists at `db/alembic/versions/004_add_company_logo.py`.
- Current Alembic head after P1-PERF-003 is `009_reco_hot_indexes`. Local upgrade, one-step downgrade, and re-upgrade passed on 2026-05-25.

## ML Model Inventory
- SBERT: multilingual SentenceTransformer default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; local fine-tuned artifact files exist under ignored `services/sbert/weights/fine_tuned_jupyter/`.
- NCF: online NCF/NeuMF service with JSON and `.pt` artifacts under ignored `services/ncf/weights/` and report artifacts.
- DQN: online DQN service with replay/policy artifacts under ignored `services/dqn/weights/` and report artifacts.
- Evaluation and smoke artifacts exist under `reports/` and `notebooks/training_runs/`.

## Known Working Areas
- Repository contains extensive pytest coverage and local report evidence of backend health.
- JWT access and refresh signing secrets now fail fast when missing or shorter than 32 bytes in shared auth and gateway configuration.
- Latest local backend validation: `.\.venv\Scripts\python.exe -m pytest -q` passed with `313 passed, 1 warning` after P2-001.
- Route, model, migration, and test surfaces are discoverable from current files.

## Known Broken Areas
- Frontend lint still reports warnings, but the blocking hook-order error in `frontend/src/app/recommendations/page.tsx` has been fixed and validated locally.
- Existing frontend lint warnings remain but do not fail lint.
- CORS defaults are too permissive outside Compose.
- Feedback forwarding can report queued without a durable retry outbox.
- No fresh import validation was run during this initializer, so known broken imports remain unknown.

## Current Blockers
- Dirty git state existed before this initializer: `README.md` modified and many project files untracked. Do not stage unrelated files.
- Most live project files remain untracked in git. Cleanup must not treat untracked files as unused.
- `frontend/` is a nested Git repository. Frontend code fixes must be committed inside `frontend/` as well as recorded in root `docs/agent/`.

## Last Completed Task
`P2-001` - validated JWT secret configuration. Commit pending.

## Next Task
Commit `P2-001`, then create the required survival checkpoint and start `P2-002`: CORS hardening.
