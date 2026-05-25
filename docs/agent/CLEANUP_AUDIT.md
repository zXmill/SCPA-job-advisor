# Cleanup Audit

Updated: 2026-05-25 19:55 +07

Task: `P0-001`

This is a read-only audit. No files were moved or deleted.

## High-Risk Repository State
- `git ls-files` currently shows only `README.md`, `AGENTS.md`, and `docs/agent/*` as tracked.
- Most live project files are untracked, including `frontend/`, `services/`, `db/`, `tests/`, `docker-compose.yml`, dependency files, CI, and most docs.
- Therefore, untracked status is not evidence that a file is unused. Cleanup must be based on runtime/import evidence, not git status alone.

## Must Keep
These are required for runtime, tests, docs, or known thesis evidence.

- Root runtime/config: `.env.example`, `.gitignore`, `.github/`, `alembic.ini`, `docker-compose.yml`, `pytest.ini`, `requirements.txt`, `requirements-db.txt`, `requirements-notebooks.txt`.
- Frontend application: `frontend/`, including `frontend/package.json`, lockfile, Next config, app routes, components, libs, public logo assets, and TypeScript config.
- Backend and ML services: `services/gateway/`, `services/pipeline/`, `services/scraper/`, `services/sbert/`, `services/ncf/`, `services/dqn/`, `services/hybrid/`, `services/shared/`, and `services/evaluation/`.
- Database layer: `db/models.py`, `db/seed.py`, `db/migrations/`, `db/alembic/`, and `db/tests/`.
- Tests: `tests/` and `db/tests/`.
- Sample data used by tests/pipeline: `data/sample/`.
- Operational scripts referenced by tests: `scripts/run_full_pipeline.py`, `scripts/sample_dataset.py`, `scripts/evaluate_sample_pipeline.py`, `scripts/retrain_models.py`, `scripts/build_ml_readiness_notebook.py`, `scripts/generate_ml_readiness_assets.py`, `scripts/bootstrap_ml_weights.py`.
- Other operational scripts: `scripts/bootstrap_db.py`, `scripts/setup_database.py`, `scripts/validate_database.py`, `scripts/verify_project.py`, `scripts/retrain_pipeline.py`, `scripts/demo_pipeline.py`.
- Infrastructure and assets: `infra/`, `logo/`, `secrets/README.md`.
- Durable agent state: `AGENTS.md`, `docs/agent/`.
- Architecture/product/security/testing docs under `docs/`, including ADRs, database/security/infrastructure/testing/debugging docs, and `reports/full_code_review_research_potential_report.md`.
- Thesis/evidence sources currently referenced by notebooks or docs: `SCPA_Backend_ML_Plan.md`, `TA_IBNU_SESUAI_Pedoman_Final.pdf`, `2206.07290v1.pdf`, `2306.02841v4.pdf`, `On_Normalised_Discounted_Cumulative_Gain_as_an_Off.pdf`, `mhealth_v10i8e37290.pdf`.

## Safe To Move Candidates
Move only after one final import/reference check. Suggested destination: `testing/archive/`.

- Root browser/debug outputs: `browser_screenshots/`.
- One-off browser/debug scripts with no detected imports: `browser_e2e.py`, `check_overflow.py`, `check_scrape.py`.
- Manual scraped-data loader pair: `insert_scraped.py` and `scrape_1000.json`; keep together if archived because the script opens that JSON by absolute path.
- Probe/check helper scripts that appear manual-only: `scripts/_add_sources.py`, `scripts/_check_auth_db.py`, `scripts/_check_db.py`, `scripts/_check_jobs_schema.py`, `scripts/_cleanup_test_users.py`, `scripts/_ensure_test_db.py`, `scripts/_health.py`, `scripts/_probe_user.py`, `scripts/_probe_user_full.py`, `scripts/_smoke_auth_realdb.py`, `scripts/check_tables.py`, `scripts/realtime_test.py`, `scripts/swarm_test.py`, `scripts/view_data.py`.

## Safe To Delete Candidates
Do not delete in this audit. These are local generated/cache artifacts and can be deleted later if no running process needs them.

- Python caches: `__pycache__/`, `db/**/__pycache__/`, `scripts/__pycache__/`, `services/**/__pycache__/`, `tests/__pycache__/`.
- Test/cache outputs: `.pytest_cache/`, `.coverage`, `.coverage_html_auth/`, `tmp/`.
- Local dependency installs: `.venv/`, `node_modules/`.
- Local secret file: `.env` must never be committed; delete only if the user confirms it is no longer needed locally.
- Ignored transient log: `browser_screenshots/browser_e2e_results.log`.

## Unsure
Leave these in place until the owner confirms intent or a deeper dependency check proves they are unused.

- `SCPAv2/`: appears to be a full alternate/parallel implementation with its own Docker Compose, frontend, package lock, source tree, tests, notebooks, and model artifacts. It is not referenced by the main app scan, but it may be thesis evidence or a migration target.
- Root `package.json` and `package-lock.json`: root package currently only declares `effect`; frontend has its own package. Keep until the intended root Node workspace role is clarified.
- `.coveragerc`: likely useful for coverage, but not validated against current pytest workflow in this task.
- Tool/editor metadata: `.devin/`, `.windsurf/`, `.claude/`, `.omc/`.
- Root thesis/defense documents: `TA_IBNU_SESUAI_Pedoman_Final.docx`, `thesis_code_review_defense.md`, and `SCPAv2/thesis_code_review_defense.md`.
- `db/alembic/versions/004_add_company_logo.py`: possible duplicate/legacy migration beside `db/migrations/004_add_company_logo.py`; do not move until Alembic configuration is tested.
- Generated report directories under `reports/`: many are generated, but they may be thesis evidence. Prefer indexing or relocating only after deciding which reports are source-of-truth deliverables.
- Service notebooks: `services/*/*.ipynb`; likely exploratory or training docs, but may be part of thesis evidence.
- Top-level notebooks: `notebooks/*.ipynb`; known deliverables from prior work, so leave unless explicitly superseded.

## Generated Artifacts
These should generally not be treated as source code.

- Reports and images: `reports/**/*.png`, `reports/**/*.csv`, `reports/**/*.json`.
- Model/checkpoint artifacts: `reports/**/*.pt`, `services/*/weights/`, `*.safetensors`.
- Notebook run outputs: `notebooks/data/`, `notebooks/training_runs/`.
- Browser screenshots: `browser_screenshots/*.png`, `reports/browser_e2e_live_*/**/*.png`.
- Root PDFs/DOCX are external evidence documents, not generated build artifacts.

## Test, Demo, Experimental
- `tests/` and `db/tests/` are active test code and must stay.
- `scripts/demo_pipeline.py`, `scripts/evaluate_sample_pipeline.py`, and `scripts/run_full_pipeline.py` are demo/evaluation entry points but are imported by tests or CI-style flows, so keep.
- `browser_e2e.py`, `check_overflow.py`, `check_scrape.py`, and probe/check scripts are manual diagnostic candidates for archive.
- `SCPAv2/` is experimental or parallel-project shaped, but too large and potentially valuable to move without owner approval.

## Recommended P0-002 Scope
Conservative safe-cleanup scope:

1. Create `testing/archive/`.
2. Move only manual/debug candidates that have no imports: root browser/debug scripts, `browser_screenshots/`, and probe/check helper scripts.
3. Do not move `SCPAv2/`, notebooks, reports, PDFs, docs, services, tests, migrations, or generated model/evaluation evidence in the first cleanup pass.
4. Run the planned validation after any move: backend tests, frontend lint/build, and Docker Compose config where available.

## Do Not Repeat
- Do not equate untracked with unused in this repo.
- Do not delete generated model/report evidence during cleanup.
- Do not move files referenced by tests without updating tests and validating.
