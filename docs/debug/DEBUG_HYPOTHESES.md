# Debug Hypotheses

Updated: 2026-05-31 09:12 +07

Status: initialized. Full hypothesis set will be generated after static inventory and baseline validation.

## Seed Hypotheses

### H1-FRONTEND-ROUTES
Hypothesis: one or more Next.js routes render runtime errors, hydration errors, or failed API calls when visited without seeded auth state.

Expected: public pages load cleanly and protected pages redirect or show controlled auth states.

Actual: unknown until Selenium audit runs.

Test: run Chrome/Selenium route audit against the frontend and record screenshots, console logs, and network failures.

Evidence location: `reports/debug/browser/` and `docs/debug/DEBUG_BROWSER_REPORT.md`.

### H1-API-INPUTS
Hypothesis: some API routes still accept malformed or empty payloads that cause 500 responses rather than controlled 4xx responses.

Expected: invalid inputs return stable 4xx responses with safe error bodies.

Actual: unknown until route smoke audit runs.

Test: route inventory plus valid/invalid request probes for discovered endpoints.

Evidence location: `docs/debug/DEBUG_API_REPORT.md`.

### H1-ML-FALLBACKS
Hypothesis: at least one ML service path depends on missing artifacts or fallback mode and needs explicit runtime evidence.

Expected: model health exposes artifact/fallback status and smoke inputs return controlled outputs.

Actual: unknown until ML smoke audit runs.

Test: SBERT, NCF, DQN, and calibrator smoke checks with shape/type/latency notes.

Evidence location: `docs/debug/DEBUG_MODEL_REPORT.md`.
