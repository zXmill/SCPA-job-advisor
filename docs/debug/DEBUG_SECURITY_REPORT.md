# Debug Security Report

Updated: 2026-05-31 09:12 +07

Status: baseline static/test evidence recorded; active runtime probes pending.

## Required Checks
- Exposed internal ports.
- Auth and admin protections.
- JWT secret validation.
- CORS production behavior.
- Scraper SSRF protections.
- Secret leakage and committed credential scan.

## Baseline Evidence
- Existing automated tests include JWT validation, CORS config, internal service auth, pipeline execution auth, company-logo host allowlist, and scraper SSRF guard tests.
- Full backend suite passed, including `tests/test_security.py`, `tests/test_cors_config.py`, `tests/test_internal_service_auth.py`, `tests/test_pipeline_execution_auth.py`, `tests/test_ssrf_guard.py`, and `tests/test_jobs_upsert.py`.
- Docker compose publishes only gateway on host port 9000 from the compose file; internal service host exposure still needs runtime network verification.

## Open Probes
- Confirm admin-only behavior for `GET /api/admin/model-health`.
- Confirm gateway `/pipeline/run` is admin-only while pipeline `/pipeline/run` requires internal token.
- Confirm production CORS and missing/weak JWT secret fail-fast behavior in process-level smoke tests.
- Confirm scraper URL endpoint blocks unsafe redirect/private IP behavior in runtime, not just unit tests.
