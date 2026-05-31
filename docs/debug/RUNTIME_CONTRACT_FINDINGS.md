# Runtime Contract Findings

Updated: 2026-05-31 21:09 +07

Status: recovery, manual-finding intake, and first runtime audit complete. No product-code changes have been made in this phase.

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
