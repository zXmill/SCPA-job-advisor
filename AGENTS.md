# SCPA Agent Instructions

## Project Overview
SCPA is a Dockerized career recommendation system. It has a Next.js frontend, a FastAPI gateway, scraper, SBERT, NCF, DQN, hybrid/pipeline services, PostgreSQL models and Alembic migrations, notebooks, reports, and pytest coverage.

## Install Dependencies
- Python: create or reuse `.venv`, then run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Frontend: run `npm install` in `frontend/`.
- Docker: copy `.env.example` to `.env`, fill required secrets and database URLs, then run Docker Compose commands from the repo root.

## Run Services
- Full stack: `docker compose up --build`.
- Gateway: `python -m uvicorn services.gateway.main:app --host 127.0.0.1 --port 8000`.
- Pipeline: `python -m uvicorn services.pipeline.main:api --host 127.0.0.1 --port 8005`.
- Frontend: run `npm run dev` in `frontend/`.

## Test, Lint, Build
- Backend tests: `.\.venv\Scripts\python.exe -m pytest -q`.
- Migrations: `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads`; use `upgrade head` when a database is available.
- Frontend lint/build: run `npm run lint` and `npm run build` in `frontend/`.
- Docker config: `docker compose config`.

## Engineering Conventions
- Trust repository files over chat history or compact summaries.
- Keep changes small, scoped, and validated.
- Work on one active task at a time using `/docs/agent/TASK_QUEUE.json`.
- Update `/docs/agent/` state before and after large or risky work.

## Security Rules
- Never commit `.env`, private tokens, API keys, credentials, or generated secret files.
- Treat gateway/frontend as public surfaces; scraper, model, and pipeline services are internal unless proven otherwise.
- Do not weaken auth, CORS, SSRF, or service-boundary checks without a written decision and validation.

## Git Commit Rules
- Commit after each meaningful completed task.
- Before committing, run `git status`, inspect the diff, run relevant validation, and update `/docs/agent/`.
- Stage only files intentionally touched in the current task.
- Use specific commit messages such as `docs: initialize codex long-running project state`.

## Definition Of Done
- The task status, touched files, validation result, and commit hash are recorded in `/docs/agent/`.
- Relevant tests, lint, build, migration, or config checks have passed, or failures are recorded in `FAILURE_LEDGER.md`.
- No unrelated user or generated work was reverted.

Long-running state lives in `/docs/agent/`.
