# Debug Frontend Report

Updated: 2026-05-31 09:12 +07

Status: static/lint/build checks completed; browser-backed checks pending.

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
- Browser failure originates from backend feedback persistence, not a frontend crash: `/recommendations` remains visible but `POST /api/recommendations/feedback` returns 500.
