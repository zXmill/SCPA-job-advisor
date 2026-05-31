# Debug Backend Report

Updated: 2026-05-31 09:12 +07

Status: baseline static/import/test checks completed.

## Required Checks
- Gateway, pipeline, scraper, SBERT, NCF, DQN, and hybrid services.
- Import errors and dependency issues.
- Runtime exceptions and failed background jobs.
- Pipeline/scraper smoke behavior.

## Baseline Results
- `scripts/verify_project.py --only import compile`: pass. Imported scraper, SBERT, NCF, DQN, pipeline, evaluation metrics, and selected scripts; compileall passed for `services`, `scripts`, and `tests`.
- Full backend tests: pass, `389 passed, 3 warnings`.
- Existing container gateway health: pass on `http://127.0.0.1:9000/health`.
- Existing container readiness: pass on `http://127.0.0.1:9000/ready`, with pipeline telemetry present.

## Warnings
- PyPDF2 deprecation warning.
- Intentional wrong-secret JWT test emits an insecure key length warning.
- Torch dataloader pin-memory warning on CPU-only environment.

## Runtime Caveat
The healthy Docker containers were created before this session and the current checkout fails to rebuild the gateway image. Container health is environment evidence, not current-image validation.
