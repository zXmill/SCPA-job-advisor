# Debug Inventory

Updated: 2026-05-31 09:12 +07

Status: initialized. Static inventory will be expanded from repository files during the baseline phase.

## Backend
- Gateway: `services/gateway/`, FastAPI public API and auth boundary.
- Pipeline: `services/pipeline/`, FastAPI orchestration and recommendation stages.
- Scraper: `services/scraper/`, scraper endpoints and extraction logic.
- SBERT: `services/sbert/`, semantic embedding/matching service.
- NCF: `services/ncf/`, collaborative filtering service.
- DQN: `services/dqn/`, skill/career action policy service.
- Hybrid: `services/hybrid/`, hybrid scoring service.
- Shared/database code: `services/shared/`, `db/`.

## Frontend
- App root: `frontend/`, nested Git repository.
- Framework: Next.js/React/TypeScript from repository state; exact route/component inventory pending static scan.

## ML
- SBERT fine-tuned runtime artifact: `models/sbert-indonesian-hybrid-manual-research/best`.
- NCF/NeuMF, DQN, calibration, and aggregation inventories pending static scan.

## Database
- Alembic config: `alembic.ini`.
- Migration folders: `db/migrations/`, `db/alembic/`.
- ORM/table inventory pending static scan.

## Infrastructure
- Docker Compose: `docker-compose.yml`.
- Environment examples and service Dockerfiles pending scan.

## CI
- Workflow inventory pending scan.
