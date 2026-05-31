# Debug Frontend Report

Updated: 2026-05-31 21:09 +07

Status: static/lint/build checks completed, route-level browser audit passed, and runtime-contract browser checks are active.

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
