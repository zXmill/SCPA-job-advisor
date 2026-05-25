# Failure Ledger

## 2026-05-25 20:12 +07 - Frontend lint hook-order failure
- Error message: `React Hook "useCallback" is called conditionally. React Hooks must be called in the exact same order in every component render.`
- Command that caused it: `npm run lint` in `frontend/`.
- Root cause: `markImpressed = useCallback(...)` is declared after `if (authLoading || !user) return (...)` in `frontend/src/app/recommendations/page.tsx`.
- Fix attempted: Moved `markImpressed = useCallback(...)` above the auth early return.
- Final fix if solved: `npm run lint` exits 0 with warnings only; `npm run build` exits 0.
- Related files: `frontend/src/app/recommendations/page.tsx`.
- Do not repeat notes: Hooks must be declared before any conditional return in the component body.
