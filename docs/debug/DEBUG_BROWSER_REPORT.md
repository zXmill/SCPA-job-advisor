# Debug Browser Report

Updated: 2026-05-31 09:12 +07

Status: Selenium/Chrome audit harness added and canonical authenticated audit completed.

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

## Canonical Authenticated Audit
- Command: `python scripts/debug/selenium_full_audit.py --output reports\debug\browser --headless --email <demo-email> --password <redacted> --settle-seconds 7`.
- Auth source: demo credentials visibly advertised on `/auth`.
- Auth result: success; token present in browser storage.
- Routes audited: 9.
- Console errors: 1.
- Network failures: 1.
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
- `/recommendations`: loaded, but `POST /api/recommendations/feedback` returned HTTP 500 during impression tracking.
- `/jobs/{sample_id}`: loaded; no network failures.

## Findings
- `BROWSER-FEEDBACK-500`: authenticated recommendation impression tracking fails with HTTP 500. Gateway logs show a foreign-key violation on `feedback_events.slate_id` because the returned `recommendation_id`/served slate ID has no matching row in `served_slates`.
- `BROWSER-LOCALHOST-CONTRACT`: audits against `127.0.0.1` created false positives or CORS/login mismatch. The working local browser contract is `localhost:3000` -> `localhost:9000`, matching `frontend/.env.local` and compose CORS.
- `BROWSER-WARN-THREE-CLOCK`: Chrome console reports `THREE.Clock` deprecation from the frontend animation stack. Non-blocking warning.

## Artifact Files
- `reports/debug/browser/browser_audit.md`
- `reports/debug/browser/summary.json`
- `reports/debug/browser/console.ndjson`
- `reports/debug/browser/network_failures.ndjson`
- `reports/debug/browser/screenshots/*.png`
