# Debug Inventory

Updated: 2026-05-31 09:12 +07

Status: static inventory pass completed from repository files.

## Backend
- Gateway: `services/gateway/main.py`, FastAPI public API and auth boundary. Routes include `/`, `/health`, `/ready`, `/api/company-logo`, admin model health, skills search, auth register/login/me, profile/completeness/onboarding/CV/certificates, jobs, job alerts, saved/skip actions, applications, market demand, learning path, recommendations, recommendation feedback, skill gap, experiments, and event tracking.
- Pipeline: `services/pipeline/main.py`, internal-token orchestration API. Routes: `/health`, `/pipeline/run`, `/training/status`, `/training/run-once`, `/feedback`, `/pipeline/invalidate-user/{user_id}`.
- Scraper: `services/scraper/main.py`. Routes: `/health`, `/scrape/html`, `/scrape/url`, `/scrape/run`, `/sample`.
- SBERT: `services/sbert/main.py`. Routes: `/health`, `/match/semantic`, `/encode`, `/metrics`.
- NCF: `services/ncf/main.py`. Routes: `/health`, `/jobs/upsert`, `/feedback`, `/train`, `/predict`, `/recommend/ncf`, `/users/{user_id}/invalidate`, `/model/status`, `/metrics`.
- DQN: `services/dqn/main.py`. Routes: `/health`, `/jobs/upsert`, `/rank`, `/learning-path`, `/rerank`, `/reward`, `/feedback`, `/recommend/dqn`, `/feedback/dqn`, `/train`, `/model/status`, `/metrics`.
- Hybrid: `services/hybrid/main.py`. Routes: `/health`, `/metrics`, `/recommend/hybrid`.
- Shared/database code: `services/shared/`, `db/`.

## Frontend
- App root: `frontend/`, nested Git repository.
- Framework: Next.js 16.2.6, React 19.2.4, TypeScript, Tailwind v4.
- App routes: `/`, `/_not-found`, `/analytics`, `/apply`, `/auth`, `/dashboard`, `/jobs/[id]`, `/onboarding`, `/profile`, `/recommendations`.
- Route files: `frontend/src/app/page.tsx`, `analytics/page.tsx`, `apply/page.tsx`, `auth/page.tsx`, `dashboard/page.tsx`, `jobs/[id]/page.tsx`, `onboarding/page.tsx`, `profile/page.tsx`, `recommendations/page.tsx`, plus root layout/error/not-found.
- Components: `AmbientBackground`, `AppLayout`, shared `Navbar`/`Footer`, UI `Avatar`, `Badge`, `Button`, `CompanyLogo`, `EmptyState`, `GlassCard`, `Input`, `Logo`, `MatchDonut`, `MatchScore`, `PageHeader`, and `Pagination`.
- API/client state: `frontend/src/lib/api.ts`, `auth-context.tsx`, `theme-context.tsx`, formatters, mock data, design tokens, and shared types.

## ML
- SBERT fine-tuned runtime artifact: `models/sbert-indonesian-hybrid-manual-research/best`.
- SBERT metrics/artifacts: `models/sbert-indonesian-hybrid-manual-research/artifacts/*.json`, `*.csv`, and best/final model directories.
- NCF/NeuMF artifacts: `services/ncf/weights/ncf_model.pt`, `online_neumf.pt`, `online_ncf.json`, `ncf_manifest.json`, `metrics.json`.
- DQN artifacts: `services/dqn/weights/dqn_model.pt`, `online_dqn.json`, `dqn_manifest.json`, `metrics.json`.
- Calibration smoke artifact: `reports/ml/calibration_layer_smoke.json`.
- Existing smoke reports: `reports/sbert_smoke/`, `reports/ncf_smoke/`, `reports/dqn_smoke/`.

## Database
- Alembic config: `alembic.ini`.
- Migration folders: `db/migrations/`, `db/alembic/`.
- Current Alembic head from local command: `012_ab_testing_and_monitoring`.
- Migrations detected: `001_initial_schema.py` through `012_ab_testing_and_monitoring.py`.
- Legacy duplicate version folder detected: `db/alembic/versions/004_add_company_logo.py`.
- Model/table coverage is tested under `db/tests/test_models.py`.

## Infrastructure
- Docker Compose: `docker-compose.yml`.
- Compose services: `postgres`, `sbert`, `scraper`, `dqn`, `ncf`, `pipeline`, `gateway`.
- Host port exposure in current compose: gateway `9000:8000`; other services are internal in compose.
- Service Dockerfiles: gateway, scraper, SBERT, NCF, DQN, pipeline.
- Root `.dockerignore`: missing during baseline, causing very large gateway build context.
- Dependency files: top-level `requirements.txt`, `requirements-db.txt`, `requirements-notebooks.txt`, service requirements, root `package.json`, and `frontend/package.json`.

## CI
- GitHub Actions: `.github/workflows/ci.yml`.
- CI runs Python 3.12, Node 22, pip install from top-level `requirements.txt`, import/compile verification, Alembic upgrade, backend pytest, frontend lint, and frontend build.
