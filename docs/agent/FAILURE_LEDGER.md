# Failure Ledger

## 2026-05-25 20:12 +07 - Frontend lint hook-order failure
- Error message: `React Hook "useCallback" is called conditionally. React Hooks must be called in the exact same order in every component render.`
- Command that caused it: `npm run lint` in `frontend/`.
- Root cause: `markImpressed = useCallback(...)` is declared after `if (authLoading || !user) return (...)` in `frontend/src/app/recommendations/page.tsx`.
- Fix attempted: Moved `markImpressed = useCallback(...)` above the auth early return.
- Final fix if solved: `npm run lint` exits 0 with warnings only; `npm run build` exits 0.
- Related files: `frontend/src/app/recommendations/page.tsx`.
- Do not repeat notes: Hooks must be declared before any conditional return in the component body.

## 2026-05-25 20:13 +07 - SSRF focused test allowlist gap
- Error message: `HTTPException: 400: scraper URL host is not allowed` for `https://id.jobstreet.com/id/jobs`.
- Command that caused it: `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`.
- Root cause: The SSRF allowlist included `jobstreet.co.id` but not the existing scraper seed host suffix `jobstreet.com`.
- Fix attempted: Add `jobstreet.com` to `SCRAPER_ALLOWED_HOST_SUFFIXES`.
- Final fix if solved: Added `jobstreet.com` to the SSRF allowlist; focused SSRF tests passed with `9 passed`.
- Related files: `services/scraper/main.py`, `tests/test_ssrf_guard.py`.
- Do not repeat notes: Keep SSRF allowlist aligned with `SOURCE_URL_TEMPLATES` and existing seed hosts.
