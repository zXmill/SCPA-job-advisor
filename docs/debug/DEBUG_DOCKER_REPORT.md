# Debug Docker Report

Updated: 2026-06-01 19:21 +07

Status: full rebuild and current runtime now pass.

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
- Initial `docker compose up -d --build`: fail.

## Fixed Build Failures
- ID: H1-DOCKER-GATEWAY-REQ.
- Evidence before fix: gateway build copied root `requirements.txt`; pip failed with `Could not open requirements file: requirements-db.txt`.
- Fix: `services/gateway/Dockerfile` now copies `services/gateway/requirements.txt`, installs service runtime requirements, copies only the gateway/shared/taxonomy package paths it imports, and starts `uvicorn services.gateway.main:app`.
- Verification: `docker compose build gateway` passed; gateway import smoke inside the image printed `SCPA Gateway`.

- ID: H2-DOCKER-CONTEXT.
- Evidence before fix: root gateway build context transfer reached about 5.06GB.
- Fix: added root `.dockerignore` excluding generated data, models, reports, notebooks, frontend/node artifacts, secrets, local env files, and bulky documents.
- Verification: gateway build context dropped to 286.56KB on direct build and 3.13KB on cached compose rebuild.

- ID: H3-DOCKER-GATEWAY-CMD.
- Evidence before fix: gateway Dockerfile command used `uvicorn main:app` while the root-context app path is `services.gateway.main:app`.
- Fix/verification: command now uses `services.gateway.main:app`; rebuilt `scpa-gateway-1` reports command `uvicorn services.ga...` and health endpoint returns 200.

- ID: H5-DOCKER-PIPELINE-PACKAGE.
- Evidence during full compose verification: after gateway repair, pipeline container restarted with `ModuleNotFoundError: No module named 'services'` from `stage_5_aggregate.py`.
- Root cause: pipeline image ran `python main.py` from `/app` but stage 5 imports `services.pipeline.calibration`.
- Fix: compose now builds pipeline from the root context and `services/pipeline/Dockerfile` copies `services/pipeline` as a package and starts `uvicorn services.pipeline.main:api`.
- Verification: `docker compose up -d --build` passed; all services are healthy.

## Current Runtime Verification
- `docker compose up -d --build`: pass.
- `docker compose ps`: postgres, scraper, SBERT, NCF, DQN, pipeline, and gateway are healthy.
- `GET http://127.0.0.1:9000/health`: `{"status":"healthy","service":"gateway"}`.
- `GET http://127.0.0.1:9000/ready`: gateway reports pipeline healthy with downstream scraper/SBERT/NCF/DQN URLs.

## Runtime Caveat
The current containers now come from the repaired build path. Browser artifacts were refreshed against this runtime.

## Continuous Scraper Worker Profile
- Updated: 2026-06-01 19:21 +07.
- Added `scraper-worker` service under the Docker Compose `continuous` profile.
- Runtime design: the worker runs `python -m services.pipeline.continuous_scraper --run-forever` as a separate process; it does not turn `/scrape/run` into an infinite request handler.
- Dependencies: `postgres` and `scraper` health checks only. It does not require SBERT, NCF, DQN, or gateway to start continuous collection.
- Evidence volume: `./reports/debug/continuous_scrape:/app/reports/debug/continuous_scrape`.
- Config validation passed:
  - `docker compose config --quiet`
  - `docker compose --profile continuous config --quiet`
- Build validation passed: `docker compose build pipeline scraper-worker`.
- Bounded runtime validation passed:
  - `docker compose --profile continuous run --rm ... --test-max-cycles 1`
  - `docker compose --profile continuous run --rm ... --test-max-cycles 2`
- Final guard from Docker runtime: 8 Kalibrr DB rows, 8 distinct source URLs, no sample/short/no-skill/missing-source rows, and API total matches DB total.
