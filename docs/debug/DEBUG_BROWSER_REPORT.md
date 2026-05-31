# Debug Browser Report

Updated: 2026-05-31 21:20 +07

Status: route-level Selenium/Chrome audit passed against rebuilt Docker runtime. A bounded runtime-contract audit is now active because manual browser inspection found user-visible timeout/cancellation issues not covered by the prior harness.

## Required Coverage
- Home page.
- Login/register when present.
- Dashboard.
- Profile.
- Recommendations.
- Job detail.
- Skill gap.
- Admin/model health when present.
- Additional routes discovered from frontend routing.

## Current Notes
- Existing architecture note: `docs/debug/BROWSER_E2E_ARCHITECTURE_REVIEW.md`.
- Artifact target: `reports/debug/browser/`.
- Harness target: `scripts/debug/selenium_full_audit.py`.

## Harness
- Script: `scripts/debug/selenium_full_audit.py`.
- Browser: Chrome via Selenium 4.44.0.
- Canonical local origin: `http://localhost:3000`.
- Canonical API origin: `http://localhost:9000`.
- Output: `reports/debug/browser/`.
- Passwords are not written to reports.

## Final Canonical Authenticated Audit
- Command: `python scripts/debug/selenium_full_audit.py --output reports\debug\browser --headless --email <demo-email> --password <redacted> --settle-seconds 7`.
- Auth source: demo credentials visibly advertised on `/auth`.
- Auth result: success; token present in browser storage.
- Routes audited: 9.
- Console errors: 0.
- Network failures: 0.
- Blank pages: 0.
- Hydration errors: 0.
- Screenshots: `reports/debug/browser/screenshots/`.

## Route Results
- `/`: loaded; no network failures.
- `/analytics`: loaded; no network failures.
- `/apply`: loaded; no network failures.
- `/auth`: loaded; no network failures.
- `/dashboard`: loaded; no network failures.
- `/onboarding`: loaded; no network failures.
- `/profile`: loaded; no network failures.
- `/recommendations`: loaded; no network failures after served-slate persistence fix.
- `/jobs/{sample_id}`: loaded; no network failures.

## Findings
- `BROWSER-FEEDBACK-500`: fixed. Authenticated recommendation impression tracking no longer returns HTTP 500 against the rebuilt current gateway container.
- `FIX-API-FEEDBACK-SLATE`: current source persists the served slate before returning recommendations, verified by focused API/database tests, full backend tests, and final Selenium audit.
- `BROWSER-LOCALHOST-CONTRACT`: audits against `127.0.0.1` created false positives or CORS/login mismatch. The working local browser contract is `localhost:3000` -> `localhost:9000`, matching `frontend/.env.local` and compose CORS.
- `BROWSER-WARN-THREE-CLOCK`: Chrome console reports `THREE.Clock` deprecation from the frontend animation stack. Non-blocking warning.

## Current Product-Quality Gap
- The previous audit did not assert semantic UI correctness after fetch cancellation, timeout, retry, sort/filter, save/skip, repeated theme toggle, skill autocomplete, or job-detail content interactions.
- The new phase must capture evidence under `reports/debug/product_quality/` and classify manual findings before any frontend/product-code fix.

## Runtime Contract Audit Gap
- Artifact target: `reports/debug/runtime_contract/`.
- Harness: `scripts/debug/runtime_contract_audit.py`.
- Required modes: dev frontend at `http://localhost:3000` and production-mode frontend at `http://localhost:3001`, both against gateway `http://localhost:9000`.
- Required scenarios: jobs timeout state, recommendations timeout state, systemic canceled fetches, auth/me repetition, saved-request cancellation, learning-path cancellation, gateway restart resilience, production frontend restart behavior, and theme toggle persistence.

## Runtime Contract Audit Run 1
- Command: `python scripts/debug/runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`.
- Result: failed overall because 2 checks failed and production-mode login was blocked.
- Dev jobs scenario: passed; successful jobs response rendered 25 job links and no timeout text.
- Dev recommendations scenario: passed; successful recommendation response rendered recommendation cards and no timeout text.
- Dev auth/session scenario: failed; `/api/auth/me` count was 6 across 4 fast navigated routes.
- Dev theme-toggle scenario: failed; no stuck spinner was observed, but theme persistence after reload failed (`storedTheme` remained null).
- Dev gateway-restart scenario: passed; gateway became healthy and jobs page did not retain a timeout state.
- Production-mode scenarios: blocked by login automation failure; not accepted as product evidence yet.
- Canceled request events captured: 0. A targeted cancellation scenario is still required to test the user-observed DevTools cancellation pattern.

## Runtime Contract Audit Run 2
- Command: `python scripts/debug/runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`.
- Result: failed overall with 4 failed checks, 3 canceled request events, and 2 production CORS console errors.
- Dev jobs scenario: normal load still passed.
- Dev recommendations scenario: failed; `/api/recommendations` was canceled with `net::ERR_ABORTED` and final UI showed `Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.`
- Dev targeted jobs cancellation: failed; canceled `/api/jobs?experience=entry...` and `/api/jobs?experience=mid...` were captured, a later `/api/jobs?experience=senior...` response was 200, but final UI showed `Permintaan kehabisan waktu. Coba lagi.`
- Dev targeted recommendations navigation: final UI recovered with recommendation cards and no timeout; this did not capture canceled events.
- Dev auth/session: still failed bounded `/api/auth/me` count with 6 requests across 4 full navigations.
- Dev theme toggle: passed; no stuck spinner, persisted `scpa_theme=dark`, and no hydration warning.
- Dev gateway restart: passed.
- Production-mode login: blocked by CORS preflight from `http://localhost:3001` to `http://localhost:9000/api/auth/login`.

## Artifact Files
- `reports/debug/browser/browser_audit.md`
- `reports/debug/browser/summary.json`
- `reports/debug/browser/console.ndjson`
- `reports/debug/browser/network_failures.ndjson`
- `reports/debug/browser/screenshots/*.png`
