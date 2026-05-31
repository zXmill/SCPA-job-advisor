# Selenium Browser Audit

- Started: 2026-05-31T03:20:06.842611+00:00
- Frontend base URL: `http://localhost:3000`
- API base URL: `http://localhost:9000`
- Sample job id: `09442211-b541-5235-a102-ca4b619faa81`
- Auth attempted: `True`
- Auth success: `True`
- Routes audited: 9
- Pages with console/network/blank-page findings: 0

## Route Results

| Route | Status | Load ms | Console errors | Network failures | Blank | Screenshot |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `/` | loaded | 7858.18 | 0 | 0 | no | `reports/debug/browser/screenshots/home.png` |
| `/analytics` | loaded | 7535.7 | 0 | 0 | no | `reports/debug/browser/screenshots/analytics.png` |
| `/apply` | loaded | 7328.69 | 0 | 0 | no | `reports/debug/browser/screenshots/apply.png` |
| `/auth` | loaded | 7437.58 | 0 | 0 | no | `reports/debug/browser/screenshots/auth.png` |
| `/dashboard` | loaded | 7366.42 | 0 | 0 | no | `reports/debug/browser/screenshots/dashboard.png` |
| `/onboarding` | loaded | 7569.31 | 0 | 0 | no | `reports/debug/browser/screenshots/onboarding.png` |
| `/profile` | loaded | 7868.14 | 0 | 0 | no | `reports/debug/browser/screenshots/profile.png` |
| `/recommendations` | loaded | 7171.08 | 0 | 0 | no | `reports/debug/browser/screenshots/recommendations.png` |
| `/jobs/09442211-b541-5235-a102-ca4b619faa81` | loaded | 7218.84 | 0 | 0 | no | `reports/debug/browser/screenshots/jobs_09442211-b541-5235-a102-ca4b619faa81.png` |

## Findings

- No console errors, network failures, or blank pages were detected.

## Auth Note

No credentials are used unless `--email` and `--password` are supplied. Passwords are never written to reports. Without credentials, protected routes are audited in no-token mode and should redirect or show controlled auth states.

## Artifact Files

- Summary JSON: `reports\debug\browser\summary.json`
- Console logs: `reports\debug\browser\console.ndjson`
- Network failures: `reports\debug\browser\network_failures.ndjson`
- Screenshots: `reports\debug\browser\screenshots`
