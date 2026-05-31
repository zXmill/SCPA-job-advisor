# Debug Frontend Report

Updated: 2026-05-31 16:26 +07

Status: static/lint/build checks completed, route-level browser audit passed, and semantic product-quality browser checks are pending.

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
