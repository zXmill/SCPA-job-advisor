# Selenium Browser Audit

- Started: 2026-05-31T02:48:56.573665+00:00
- Frontend base URL: `http://localhost:3000`
- API base URL: `http://localhost:9000`
- Sample job id: `21b292cd-508a-5820-9029-b0806fd5c22d`
- Auth attempted: `True`
- Auth success: `True`
- Routes audited: 9
- Pages with console/network/blank-page findings: 1

## Route Results

| Route | Status | Load ms | Console errors | Network failures | Blank | Screenshot |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `/` | loaded | 7529.75 | 0 | 0 | no | `reports/debug/browser/screenshots/home.png` |
| `/analytics` | loaded | 7241.06 | 0 | 0 | no | `reports/debug/browser/screenshots/analytics.png` |
| `/apply` | loaded | 7186.74 | 0 | 0 | no | `reports/debug/browser/screenshots/apply.png` |
| `/auth` | loaded | 7206.8 | 0 | 0 | no | `reports/debug/browser/screenshots/auth.png` |
| `/dashboard` | loaded | 7201.64 | 0 | 0 | no | `reports/debug/browser/screenshots/dashboard.png` |
| `/onboarding` | loaded | 7236.83 | 0 | 0 | no | `reports/debug/browser/screenshots/onboarding.png` |
| `/profile` | loaded | 7181.06 | 0 | 0 | no | `reports/debug/browser/screenshots/profile.png` |
| `/recommendations` | loaded | 7164.97 | 1 | 1 | no | `reports/debug/browser/screenshots/recommendations.png` |
| `/jobs/21b292cd-508a-5820-9029-b0806fd5c22d` | loaded | 7252.89 | 0 | 0 | no | `reports/debug/browser/screenshots/jobs_21b292cd-508a-5820-9029-b0806fd5c22d.png` |

## Findings

- `/recommendations`: 1 console errors, 1 network failures.

## Auth Note

No credentials are used unless `--email` and `--password` are supplied. Passwords are never written to reports. Without credentials, protected routes are audited in no-token mode and should redirect or show controlled auth states.

## Artifact Files

- Summary JSON: `reports\debug\browser\summary.json`
- Console logs: `reports\debug\browser\console.ndjson`
- Network failures: `reports\debug\browser\network_failures.ndjson`
- Screenshots: `reports\debug\browser\screenshots`
