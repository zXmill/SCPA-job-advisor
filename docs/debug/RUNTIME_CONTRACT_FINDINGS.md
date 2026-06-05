# Runtime Contract Findings

Updated: 2026-05-31 21:41 +07

Status: runtime contract defects reproduced, fixed where confirmed, and re-validated in dev and production-mode frontend audits.

## Scope Boundary
- Active phase: Bounded Full-Stack Runtime Contract Debugging Pass.
- In scope: runtime fetch lifecycle, timeout/cancellation classification, auth/session stability, gateway contract behavior, UI state consistency, gateway restart resilience, production-mode frontend behavior, and the isolated theme-toggle defect.
- Out of scope for this phase: broad award-style frontend redesign, skill taxonomy expansion, external datasets, scraper redesign, job-description pipeline reconstruction, ML training, recommendation model redesign, and unrelated product features.
- `impeccable` is applied as the product-UI quality lens: restrained task UI, truthful loading/error states, stable controls, no permanent spinners, no decorative redesign work during this runtime pass.

## BUG-RUNTIME-JOBS-TIMEOUT
- Observed route: job vacancies page, currently represented by `/` or the actual jobs route discovered by the audit.
- Observed UI text: `Permintaan kehabisan waktu. Coba lagi.`
- Affected endpoints: `/api/jobs?page=1&limit=25`; possible saved jobs/auth dependencies if the page loads user state.
- Expected behavior: after a successful current jobs response, job cards render and no timeout/retry state remains. Canceled stale jobs requests must not set final user-facing error state.
- Actual behavior: user manually observed a timeout message on the job vacancies page.
- Suspected layers: frontend API client AbortError classification, jobs page request cleanup, stale request overwrite, gateway latency/availability, auth/session remount behavior.
- Evidence needed: Selenium network trace, DOM snapshot, screenshot, console log, gateway log, current request status, and stale/canceled request classification in dev and production frontend modes.
- Reproduction plan: login if needed, open jobs page, wait for `/api/jobs?page=1&limit=25`, perform location/experience filtering, observe final UI state, repeat after gateway restart.
- Pass condition: jobs page never shows timeout UI after a successful current jobs response; retry appears only after a current real failure.
- Current evidence: first dev audit passed jobs checks with 25 job links rendered and no timeout text; production-mode evidence and targeted stale cancellation evidence remain pending.
- Confirmed evidence: second targeted dev audit captured canceled jobs filter requests followed by a successful jobs response, but the final UI still showed `Permintaan kehabisan waktu. Coba lagi.` and `Coba Lagi`.
- Root cause classification: frontend stale request overwrite plus AbortController cancellation treated as timeout.
- Final fix/evidence: nested frontend commit `7f746fe` adds `ApiCancellationError`, current-request sequence guards, timeout-only error rendering, and current-request-only loading cleanup in `frontend/src/app/analytics/page.tsx`. Final audit `reports/debug/runtime_contract/summary.json` passed dev and prod jobs and targeted jobs-cancellation checks with no timeout or retry text after current success.

## BUG-RUNTIME-RECOMMENDATIONS-TIMEOUT
- Observed route: `/recommendations`.
- Observed UI text: `Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.`
- Affected endpoints: `/api/recommendations`, `/api/applications`, `/api/learning-path`, `/api/auth/me`, and saved jobs endpoint.
- Expected behavior: recommendation cards render when recommendation data exists. Timeout UI appears only when the active recommendation request times out, not after stale cancellation or a later success.
- Actual behavior: user manually observed recommendation timeout text.
- Suspected layers: endpoint timeout policy, recommendation page request sequencing, AbortError handling, auth/session remount, downstream gateway/pipeline latency, production-mode mismatch.
- Evidence needed: request timings, canceled request list, gateway logs, DOM final state, recommendation response shape, sort/save/skip feedback behavior.
- Reproduction plan: login, open `/recommendations`, track all related endpoints, change sort, trigger save/skip/impression, repeat after gateway restart and production frontend restart.
- Pass condition: no timeout text or `Coba Lagi` retry UI remains after successful current recommendation data.
- Current evidence: first dev audit passed recommendation checks with recommendation cards rendered and no timeout text; production-mode evidence and targeted stale cancellation evidence remain pending.
- Confirmed evidence: second dev audit captured `/api/recommendations` failing with `net::ERR_ABORTED` and final UI showing `Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.`.
- Root cause classification: frontend AbortError/current-request handling, with endpoint latency making the timeout/cancel path visible.
- Final fix/evidence: nested frontend commit `7f746fe` separates cancellation from timeout, adds current-request guards, and raises the recommendations timeout policy to 45 seconds. Final audit passed dev and prod recommendations and targeted recommendations navigation checks with recommendation cards rendered and no stale timeout UI.

## BUG-RUNTIME-CANCELED-FETCH-SYSTEMIC
- Observed route: cross-route symptom during jobs, recommendations, and authenticated navigation.
- Observed UI text: jobs and recommendations timeout messages above.
- Affected endpoints: `/api/jobs?page=1&limit=25`, `/api/recommendations`, saved jobs endpoint, `/api/applications`, `/api/learning-path`, `/api/auth/me`.
- Expected behavior: canceled requests are classified as cancellation and cannot overwrite newer success/error state.
- Actual behavior: user manually observed canceled fetches in DevTools around core endpoints.
- Suspected layers: frontend AbortController cleanup, React Strict Mode remount behavior, duplicate effects, unstable dependencies, auth provider state transitions, API client error normalization.
- Evidence needed: network entries with initiator/component source, abort reason, current route, final UI state, and whether a later success was overwritten.
- Reproduction plan: capture Selenium performance logs while navigating quickly across authenticated routes and while sorting/filtering recommendations/jobs.
- Pass condition: canceled stale requests are either ignored or reported only in diagnostics; they do not show user-facing timeout/error UI.
- Current evidence: first runtime audit captured 0 canceled request events, so this finding remains unconfirmed by harness and needs targeted cancellation reproduction.
- Confirmed evidence: second runtime audit captured 3 canceled request events. Jobs cancellation caused false final timeout UI after a later successful response; recommendation cancellation caused final timeout UI.
- Final fix/evidence: frontend request handlers now ignore stale/canceled non-timeout requests and only clear loading/error for the active request. Final audit captured 75 canceled request events across dev/prod scenarios and 0 failed checks; canceled events did not leave user-facing timeout state.

## BUG-RUNTIME-AUTH-ME-REPEAT
- Observed route: authenticated routes and reload/navigation flows.
- Observed UI text: timeout or logged-out/transient loading states if auth clears incorrectly.
- Affected endpoints: `/api/auth/me` and any page request gated by auth state.
- Expected behavior: `/api/auth/me` is not redundantly called without need; valid sessions survive reload and fast navigation; invalid sessions produce controlled logout/auth state, not cascading timeout UI.
- Actual behavior: user observed canceled fetches around `/api/auth/me`; redundancy count unknown until audit.
- Suspected layers: auth provider initialization, Strict Mode remount, token storage reads, route-level effects waiting on auth.
- Evidence needed: auth/me request count per scenario, token presence as boolean only, final route state, and no persisted auth-loading loops.
- Reproduction plan: load app with valid token, reload, navigate quickly across dashboard/profile/recommendations/jobs, then test invalid token in an isolated run.
- Pass condition: auth state stabilizes without request storms or persistent timeout/error states.
- Current evidence: first dev audit failed the bounded auth/me count check with 6 `/api/auth/me` requests across 4 fast navigated routes. Final UI had no persistent timeout text. Production-mode evidence remains pending.
- Confirmed evidence: second dev audit again counted 6 `/api/auth/me` requests across 4 full navigations. Dashboard/profile page data fetching adds avoidable `api.getMe()` calls in addition to auth-provider refresh.
- Final evidence: final audit passed the bounded auth/session check in dev and prod with 5 `/api/auth/me` requests across 4 full navigations and no persistent timeout/error state. A pre-existing untracked dashboard page in the nested frontend tree contains local request-dedup work and was not staged as part of the scoped tracked-file commit.

## BUG-RUNTIME-SAVED-REQUEST-CANCEL
- Observed route: recommendations/jobs flows that load saved state.
- Observed UI text: timeout or retry UI if saved-state request cancellation is misclassified.
- Affected endpoints: `/api/jobs/saved` or `/api/recommendations/saved` if present.
- Expected behavior: saved-state fetch cancellation cannot corrupt recommendation/jobs UI. Save/unsave actions reconcile with current state only.
- Actual behavior: user manually observed canceled fetches around saved-job endpoints.
- Suspected layers: saved-state fetch cleanup, page-level parallel request orchestration, feedback/save side effects.
- Evidence needed: network trace, endpoint status, final saved state, save/skip action logs, stale-update classification.
- Reproduction plan: open recommendations, save/unsave jobs, navigate away/back quickly, repeat after gateway restart.
- Pass condition: saved state is correct after current successful request; stale cancellation does not show timeout UI.
- Current evidence: first dev recommendations save-action check did not leave timeout UI. Canceled saved-request reproduction remains pending.
- Final evidence: final dev and prod recommendations checks passed save-action assertions with no timeout or retry UI after successful page data.

## BUG-RUNTIME-LEARNING-PATH-CANCEL
- Observed route: `/recommendations` or dashboard/profile pages that fetch learning path.
- Observed UI text: timeout/degraded recommendation state if learning path cancellation pollutes parent page state.
- Affected endpoints: `/api/learning-path`.
- Expected behavior: learning-path cancellation or transient failure is isolated to learning-path UI and does not overwrite recommendation cards or jobs state.
- Actual behavior: user manually observed canceled fetches around `/api/learning-path`.
- Suspected layers: recommendation page parallel request handling, gateway downstream latency, state coalescing.
- Evidence needed: request timings, status codes, final page state, gateway response logs.
- Reproduction plan: open `/recommendations`, wait for `/api/learning-path`, sort/change page state, then repeat during gateway restart.
- Pass condition: recommendation UI remains truthful and recoverable even if learning-path request cancels or fails transiently.
- Current evidence: first dev recommendations scenario did not leave timeout UI; targeted learning-path cancellation evidence remains pending.
- Final evidence: final dev and prod auth/navigation/recommendations scenarios exercised `/api/learning-path` as part of the route flow and passed with no parent-page timeout state.

## BUG-FE-THEME-TOGGLE-STUCK
- Observed route: global nav/app shell.
- Observed UI text: none; visual defect.
- Affected endpoints: none.
- Expected behavior: repeated theme clicks update icon/state, no spinner remains, theme persists across reload, and no hydration warning appears.
- Actual behavior: user manually observed a stuck or overlapping loading/spinner state around the theme toggle.
- Suspected layers: theme provider mounted guard, toggle component visual state, persisted theme storage, hydration behavior.
- Evidence needed: before/after/reload screenshots, DOM/class state, localStorage value, console warnings.
- Reproduction plan: load major routes, click theme toggle 5 times, reload, verify persisted theme and no stuck indicator.
- Pass condition: no permanent spinner/overlap; icon and persisted theme agree after repeated clicks and reload.
- Current evidence: first dev audit found no stuck spinner and no hydration warning, but theme persistence failed because `localStorage.scpa_theme` remained null after repeated clicks and reload.
- Updated evidence: second dev audit passed theme toggle checks after harness hardening: no stuck spinner, no hydration warning, and persisted `scpa_theme=dark` after reload. Theme product fix is deferred unless a new runtime reproduction contradicts this.
- Final evidence: final dev and prod theme-toggle scenarios passed after 5 clicks and reload: no spinner/loading indicator, `scpa_theme=dark`, and no hydration warning. No theme product-code fix was justified.

## BUG-RUNTIME-PROD-CORS-LOCALHOST-3001
- Observed route: production-mode local frontend `/auth` at `http://localhost:3001`.
- Observed UI text: login remains blocked; Chrome console reports CORS preflight failure.
- Affected endpoints: `POST /api/auth/login`.
- Expected behavior: local production-mode frontend origin used by the runtime-contract audit can call the local gateway in development.
- Actual behavior: gateway CORS defaults omit `http://localhost:3001`, so browser blocks login before authenticated production-mode scenarios can run.
- Suspected layers: gateway CORS default list, docker-compose CORS env default, `.env.example` local run docs.
- Evidence needed: post-fix production-mode audit reaches authenticated scenarios without CORS errors.
- Reproduction plan: run runtime-contract audit against `http://localhost:3001` and `http://localhost:9000`.
- Pass condition: production-mode login succeeds and no CORS console error is present for `/api/auth/login`.
- Root cause classification: local gateway/frontend runtime contract misconfiguration, not production wildcard CORS weakening.
- Final fix/evidence: root commit `305391e` adds `http://localhost:3001` to development CORS defaults, compose defaults, and `.env.example`, with `tests/test_cors_config.py` updated. Final production-mode audit login succeeded and all authenticated prod scenarios passed.

## Final Runtime Contract Resolution
- Frontend tracked product commit: `7f746fe fix: harden runtime fetch cancellation contract` in the nested `frontend/` repo.
- Root product commit: `305391e fix: allow local production frontend CORS origin`.
- Final audit command: `.\.venv\Scripts\python.exe scripts\debug\runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`.
- Final audit result: 14 scenarios, 0 failed checks, 75 canceled request events classified without stale timeout UI, and 0 severe console entries.
- Final artifacts: `reports/debug/runtime_contract/runtime_contract_report.md`, `summary.json`, `network.ndjson`, `console.ndjson`, `gateway_logs.ndjson`, screenshots, and DOM snapshots.
