# Debug Docker Report

Updated: 2026-05-31 09:12 +07

Status: config baseline completed; full rebuild failed.

## Required Checks
- Compose service inventory.
- Health checks.
- Exposed host ports.
- Service dependencies.
- Environment variable requirements.
- Network and volume wiring.

## Compose Inventory
- Services: `postgres`, `sbert`, `scraper`, `dqn`, `ncf`, `pipeline`, `gateway`.
- Published host port in compose: gateway `9000:8000`.
- Internal services expose container ports only: postgres 5432, scraper 8001, SBERT 8002, NCF 8003, DQN 8004, pipeline 8005.
- Required env vars for config validation: PostgreSQL password, gateway database URL, JWT secrets, internal service token.

## Baseline Results
- `docker compose config --services`: pass.
- `docker compose config --quiet`: pass.
- `docker compose up -d --build`: fail.

## Confirmed Build Failure
- ID: H1-DOCKER-GATEWAY-REQ.
- Evidence: compose builds gateway with root context `.` and `services/gateway/Dockerfile`; `COPY requirements.txt .` therefore copies root `requirements.txt`, not `services/gateway/requirements.txt`.
- Root `requirements.txt` references `requirements-db.txt`, `requirements-notebooks.txt`, and service requirement files that are not copied before the `pip install` layer, so pip fails with `Could not open requirements file: requirements-db.txt`.
- Additional suspected follow-up issue: the gateway Dockerfile runs `uvicorn main:app` after copying the root repository, but the app entry point is `services.gateway.main:app`. This needs verification after the dependency-layer failure is fixed.
- Additional evidence: root `.dockerignore` is missing, and the gateway build transferred about 5.06GB of context before failing.

## Runtime Caveat
Existing containers are healthy from a prior build, but they do not prove the current Docker source can build.
