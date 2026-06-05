# Debug Frontend Report

Updated: 2026-06-01 05:15 +07

Status: static/lint/build checks completed, route-level browser audit passed, runtime-contract browser checks passed, and product-quality frontend checks passed after rich jobs/skills UI fixes.

## Required Checks
- Pages/routes.
- Layouts.
- Components.
- Hooks.
- API clients.
- Forms and buttons.
- Runtime errors, hydration errors, and bad loading/error states.

## Static Route Inventory
- `/`
- `/analytics`
- `/apply`
- `/auth`
- `/dashboard`
- `/jobs/[id]`
- `/onboarding`
- `/profile`
- `/recommendations`
- `/_not-found`

## Baseline Validation
- `npm run lint`: pass, 0 errors, 16 warnings.
- `npm run build`: pass, Next.js 16.2.6 production build succeeded.
- Existing dev server: node process from `E:\TUGAS AKHIR\SCPA\frontend` is listening on port 3000.
- `frontend/.env.local` points `NEXT_PUBLIC_API_URL` to `http://localhost:9000`.

## Lint Warnings To Investigate
- Unused imports in `apply`, `auth`, `jobs/[id]`, `onboarding`, and `recommendations`.
- `frontend/src/app/recommendations/page.tsx` has two `react-hooks/exhaustive-deps` warnings for `eventContext`.
- `Avatar.tsx` uses a raw `<img>` and triggers the Next image optimization warning.

## Browser Results
- Canonical authenticated audit on `localhost:3000` loaded all discovered routes without blank pages or hydration errors.
- Browser warning: `THREE.Clock` deprecation on the home page.
- Browser warning: one LCP image recommendation on analytics for a company logo image.
- Previous browser failure originated from backend feedback persistence, not a frontend crash: `/recommendations` remained visible while `POST /api/recommendations/feedback` returned 500. This was fixed and later verified by final route-level Selenium audit.

## Product-Quality Checks Needed
- Job vacancies timeout/error state correctness.
- Recommendation timeout/error state correctness and canceled request race behavior.
- Theme toggle repeated-click and persistence behavior.
- Skill autocomplete taxonomy richness and duplicate handling.
- Job detail content depth, structured fields, and skill-gap context.

## Runtime Contract Checks Needed
- API client currently maps browser `AbortError` to a 408 timeout-style `ApiError`; runtime evidence must determine whether this causes false timeout UI for stale canceled requests.
- Auth provider calls `/api/auth/me` on mount when a token exists; runtime audit must count redundant calls and verify fast navigation/reload stability.
- Theme provider uses a mounted guard and persisted `scpa_theme`; runtime audit must verify repeated toggle and reload behavior.
- Broad frontend redesign is deferred in this phase; only runtime UI correctness and the isolated theme defect are in scope.

## Runtime Contract Audit Run 1
- Harness: `scripts/debug/runtime_contract_audit.py`.
- Dev jobs and recommendations checks passed without visible false timeout UI.
- No canceled request events were captured in the first run, so a targeted cancellation scenario is still needed before fixing cancellation handling.
- Auth/session check failed with 6 `/api/auth/me` requests during fast navigation across 4 routes.
- Theme check failed persistence after reload: the audit saw `data-theme=light` and `localStorage.scpa_theme=null` after repeated clicks and reload, while no spinner or hydration warning remained.
- Production-mode frontend checks were blocked by login automation and must be rerun after harness hardening.

## Runtime Contract Audit Run 2
- Confirmed frontend stale cancellation bug: `frontend/src/app/analytics/page.tsx` and `frontend/src/app/recommendations/page.tsx` both treat `controller.signal.aborted` as a user-facing timeout and clear current data without proving the aborted request is still current.
- Jobs reproduction: targeted filter cancellation captured 2 canceled jobs requests, then a successful jobs response, but final UI remained a timeout/retry state.
- Recommendations reproduction: `/api/recommendations` canceled with `net::ERR_ABORTED` and final UI remained the recommendation timeout message.
- Theme defect is not currently confirmed after harness hardening; repeated clicks persisted `scpa_theme=dark` and no spinner/hydration warning appeared.
- Auth/session redundancy is partially frontend-caused: full navigation remounts the auth provider, and dashboard/profile also call `api.getMe()` for page data.
- Production-mode frontend is blocked by gateway CORS, not by a browser automation failure.

## Runtime Contract Final Result
- Nested frontend commit: `7f746fe fix: harden runtime fetch cancellation contract`.
- `frontend/src/lib/api.ts` now classifies browser `AbortError` as `ApiCancellationError`, not a timeout-style `ApiError`.
- `frontend/src/app/analytics/page.tsx` and `frontend/src/app/recommendations/page.tsx` now use active request sequence guards so stale canceled requests cannot overwrite newer successful state.
- Recommendation timeout policy is 45 seconds to match hybrid gateway/model latency expectations.
- Final frontend validation:
  - `npm run lint`: pass, 0 errors with existing warnings.
  - `npm run build`: pass.
  - Runtime audit: dev and production-mode jobs/recommendations/targeted-cancellation/auth/theme/gateway-restart scenarios all passed.
- Theme toggle was tested but not changed: repeated clicks and reload persisted `scpa_theme=dark`, with no stuck spinner and no hydration warning.
- Broad award-style redesign remains deferred by runtime-contract scope; only truthful loading/error state and runtime UI consistency were changed.

## Product Quality Data/UI Final Result
- Updated: 2026-06-01 05:15 +07.
- Nested frontend commit: `999e2a8 fix: stabilize product UI for rich jobs and skills`.
- The custom product cursor overlay was removed from `AppLayout`/global CSS because the blue cursor ring matched the user's screenshots and visually overlapped the theme and skill controls.
- Theme provider state was stabilized with lazy initial theme resolution and a functional `toggleTheme()` path. Product-quality audit clicked theme controls across `/analytics`, `/recommendations`, `/profile`, and `/dashboard`; no stuck spinner remained and theme persisted after reload.
- Profile skill autocomplete now renders taxonomy-backed suggestions with aliases/categories and prevents duplicate additions. Audit checks for target queries passed.
- Job detail UI now renders structured description sections, metadata, and richer skill signals when the API exposes them; five real job detail pages were audited successfully.
- Frontend validation:
  - `npm run lint`: pass, 0 errors with 15 existing warnings.
  - `npm run build`: pass.
- Remaining frontend warnings are pre-existing lint warnings and were not in scope unless tied to a confirmed P0/P1 product-quality defect.
