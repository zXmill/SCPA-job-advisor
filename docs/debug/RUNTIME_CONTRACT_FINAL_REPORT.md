# Runtime Contract Final Report

Updated: 2026-05-31 21:41 +07

## Executive Summary
The bounded full-stack runtime contract pass is complete. The user-reported false timeout pattern was reproduced with runtime browser evidence, fixed in the tracked frontend request paths, and validated in both dev and production-mode frontend audits. A separate local production-mode CORS contract defect was confirmed and fixed in the root gateway/config layer. The theme-toggle defect was tested but not reproduced after harness hardening, so no theme product-code change was made.

Broad frontend redesign, skill taxonomy, job-description enrichment, scraper work, ML training, and recommendation model changes were intentionally deferred by scope.

## Defects Reproduced
- `BUG-RUNTIME-JOBS-TIMEOUT`: targeted jobs filter cancellation produced canceled `/api/jobs` requests, a later successful current response, and a final false timeout/retry UI before the fix.
- `BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT`: `/api/recommendations` cancellation produced final timeout text before the fix.
- `BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC`: canceled request events could affect final user-facing state.
- `BUG-RUNTIME-PROD-CORS-LOCALHOST-3001`: production-mode local frontend at `http://localhost:3001` was blocked by gateway CORS during login.
- `BUG-FE-THEME-TOGGLE-STUCK`: tested, but not reproduced in hardened/final audit.

## Root Cause Classification
- Frontend stale request overwrite.
- AbortError/cancellation handled as user-facing timeout.
- Recommendation client timeout too short for hybrid gateway/model latency envelope.
- Local gateway/frontend development CORS origin mismatch for production-mode Next.js validation.
- Theme provider isolated defect was not confirmed.

## Fixes Made
- Nested frontend commit `7f746fe fix: harden runtime fetch cancellation contract`.
  - Added `ApiCancellationError` for browser `AbortError`.
  - Added active request sequence guards in jobs and recommendations pages.
  - Ensured stale/canceled non-timeout requests do not set error, clear data, or end loading for a newer active request.
  - Raised recommendations timeout to 45 seconds with a local why-comment.
- Root commit `305391e fix: allow local production frontend CORS origin`.
  - Added `http://localhost:3001` to development CORS defaults, compose defaults, and example env.
  - Updated CORS regression expectations.

## Validation Commands
- `.\.venv\Scripts\python.exe -m py_compile services\gateway\main.py tests\test_cors_config.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_cors_config.py -q`
- `npm run lint` in `frontend/`
- `npm run build` in `frontend/`
- `docker compose config --quiet`
- `$env:CORS_ALLOWED_ORIGINS='http://localhost:3000,http://localhost:3001,http://localhost:8000'; docker compose up -d --build gateway`
- `.\.venv\Scripts\python.exe scripts\debug\runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`
- `rg -n "<redacted secret-patterns>" reports/debug/runtime_contract scripts/debug/runtime_contract_audit.py`

## Final Browser Results
- Artifact root: `reports/debug/runtime_contract/`.
- Summary: `reports/debug/runtime_contract/summary.json`.
- Report: `reports/debug/runtime_contract/runtime_contract_report.md`.
- Network trace: `reports/debug/runtime_contract/network.ndjson`.
- Console trace: `reports/debug/runtime_contract/console.ndjson`.
- Gateway logs: `reports/debug/runtime_contract/gateway_logs.ndjson`.
- Screenshots: `reports/debug/runtime_contract/screenshots/`.
- DOM snapshots: `reports/debug/runtime_contract/dom_snapshots/`.

Final audit result:
- Scenarios: 14.
- Failed checks: 0.
- Canceled request events: 75.
- Severe console entries: 0.
- Dev and production-mode jobs, recommendations, targeted cancellation, auth/session, theme toggle, and gateway-restart scenarios passed.

## Remaining Limitations
- The repository and nested frontend repo remain dirty with pre-existing unrelated modified/untracked files. This pass staged only scoped files.
- `frontend/src/app/dashboard/page.tsx` is pre-existing untracked work in the nested frontend repo. Local runtime evidence observed bounded `/api/auth/me` behavior, but the scoped frontend commit intentionally did not add the whole untracked dashboard page.
- Full security runtime probes, ML runtime smoke checks, scraper SSRF runtime probes, skill taxonomy expansion, and job-description data-quality work remain separate phases.

## Next Recommended Phase
Stop this runtime pass. Resume from repository state only and choose the next bounded phase explicitly, preferably ML runtime smoke checks or security runtime probes if those remain higher priority than product-data quality work.
