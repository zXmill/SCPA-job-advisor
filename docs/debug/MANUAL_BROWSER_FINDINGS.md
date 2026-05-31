# Manual Browser Findings

Updated: 2026-05-31 16:31 +07

Status: user-reported manual browser findings recorded before product-code changes. These issues still require independent runtime evidence from the semantic Selenium product-quality audit.

## Scope
- Frontend origin: `http://localhost:3000`.
- Gateway origin: `http://localhost:9000`.
- Evidence target: `reports/debug/product_quality/`.
- Rule: do not fix frontend/product/data code until runtime evidence confirms the root cause.

## BUG-FE-JOBS-TIMEOUT

Observed UI text:
- `Permintaan kehabisan waktu. Coba lagi.`

Affected route:
- Job vacancies page, likely `/`.

Suspected subsystem:
- Frontend jobs page fetch lifecycle, gateway `/api/jobs?page=1&limit=25`, request timeout handling, stale request cancellation, loading/error state transitions.

Expected behavior:
- The jobs page should load job cards when `/api/jobs?page=1&limit=25` returns jobs.
- A retry/timeout message should appear only after a real current request failure, not after an aborted stale request.
- No loading spinner should remain after network idle.

Actual behavior:
- User manually observed a timeout/error message on the Job Vacancies page.
- DevTools also showed canceled fetches around `/api/jobs?page=1&limit=25`.

Reproduction steps:
- Start frontend at `http://localhost:3000` and gateway at `http://localhost:9000`.
- Login if the route requires an authenticated state.
- Open the job vacancies page.
- Observe visible page text and DevTools Network for `/api/jobs?page=1&limit=25`.
- Trigger location and experience filters and observe whether stale canceled requests surface as visible errors.

Evidence still needed:
- Screenshot of the timeout state.
- DOM text snapshot.
- Network status and timing for the jobs request.
- Browser console logs.
- Server logs for the same request window.
- Frontend request lifecycle evidence showing whether an abort, timeout, remount, or stale response set the error state.

Test plan:
- Semantic Selenium audit waits for `/api/jobs?page=1&limit=25`.
- Assert no visible timeout text after a successful jobs response.
- Assert at least one job card appears when the API returns jobs.
- Assert retry appears only after an actual current request failure.
- Classify canceled requests as expected stale cancellation or unexpected user-visible failure.

## BUG-FE-RECOMMENDATIONS-TIMEOUT

Observed UI text:
- `Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.`

Affected route:
- `/recommendations`.

Suspected subsystem:
- Frontend recommendations page fetch lifecycle, gateway `/api/recommendations`, saved jobs/applications/learning-path/auth requests, model/pipeline latency tolerance, request timeout handling.

Expected behavior:
- The recommendations page should show recommendation cards when recommendation data returns successfully.
- A model timeout message should appear only when the current recommendation request actually times out.
- A successful newer request must clear any stale prior timeout state.

Actual behavior:
- User manually observed the AI matching timeout/error message on the Recommendations page.
- DevTools showed canceled fetches around `/api/recommendations` and related page bootstrapping endpoints.

Reproduction steps:
- Start frontend and gateway.
- Login using a valid demo or test account.
- Open `/recommendations`.
- Observe network calls for `/api/recommendations`, `/api/applications`, `/api/learning-path`, `/api/auth/me`, and saved jobs endpoint.
- Change sort order and click save/skip/impression-producing actions.

Evidence still needed:
- Screenshot of the timeout state.
- DOM text snapshot.
- Network waterfall for recommendation and related requests.
- Console logs and hydration warnings.
- Server logs and gateway recommendation latency.
- Frontend request lifecycle evidence showing whether a canceled stale request overwrites a newer successful state.

Test plan:
- Semantic Selenium audit waits for recommendation-related endpoints.
- Assert no visible timeout message after successful API data.
- Assert cards render when API returns recommendation data.
- Assert `Coba Lagi` is absent after success.
- Check sort changes do not create a refetch storm.
- Check save/skip/impression feedback does not create stale-error UI.

## BUG-FE-CANCELED-FETCH-RACE

Observed UI text:
- DevTools Network shows canceled fetches around `/api/jobs?page=1&limit=25`, `/api/recommendations`, `/api/jobs/saved` or `/api/recommendations/saved`, `/api/applications`, `/api/learning-path`, and `/api/auth/me`.

Affected route:
- `/`, `/recommendations`, and likely other authenticated routes that share auth/profile/saved-job fetches.

Suspected subsystem:
- Frontend API client, AbortController usage, React Strict Mode remounts, route changes, duplicated useEffect dependencies, auth context bootstrapping, page-level fetch cleanup.

Expected behavior:
- Expected cancellations should be ignored or classified as stale.
- Aborted stale requests must not set visible timeout/error state after a newer request is active or successful.
- Request state transitions should be monotonic per request source.

Actual behavior:
- User manually observed canceled requests near routes that also show timeout/error UI.
- It is not yet proven whether cancellations are expected dev-mode cleanup or unexpected stale-error writes.

Reproduction steps:
- Load each affected route in the frontend.
- Open DevTools Network and Console.
- Navigate between `/`, `/recommendations`, `/dashboard`, and `/profile`.
- Trigger filters, sort, save, skip, and reload actions.
- Capture canceled request timing relative to visible UI errors.

Evidence still needed:
- Browser network logs with initiator/source classification.
- Component lifecycle logs for mount/unmount and request abort.
- Per-request sequence IDs showing stale/current status.
- Console logs for AbortError, timeout, and state-update-after-unmount paths.

Test plan:
- Add temporary debug instrumentation around frontend API requests and affected pages after baseline evidence is captured.
- Record request id, endpoint, source, start, abort, success, failure, timeout, route, mounted status, and stale-state ignore decisions.
- Assert canceled stale requests do not produce user-facing timeout or retry UI.

## BUG-FE-THEME-TOGGLE-STUCK

Observed UI text:
- No explicit text; user reported the dark/light theme icon or spinner appears stuck or overlaps the button.

Affected route:
- Global app shell/navigation on every major route.

Suspected subsystem:
- Theme provider, mounted guard, localStorage/cookie persistence, toggle button rendering, spinner/icon conditional rendering, hydration handling.

Expected behavior:
- Clicking the theme toggle should switch between light and dark states reliably.
- The visible icon should match the active theme.
- Any loading or mounted-state placeholder must disappear after hydration.
- Theme choice should persist after reload without hydration warnings or layout overlap.

Actual behavior:
- User manually observed a visual/loading bug where the icon or spinner appears stuck or overlaps the button.

Reproduction steps:
- Load a major route.
- Observe initial theme icon and localStorage/cookie state.
- Click the theme toggle five times.
- Reload the route.
- Repeat on `/`, `/recommendations`, `/profile`, and `/dashboard`.

Evidence still needed:
- Before/after screenshots.
- DOM snapshot of the toggle button.
- Computed classes and spinner/icon visibility.
- localStorage/cookie values before clicks, after clicks, and after reload.
- Console logs for hydration warnings.

Test plan:
- Semantic Selenium audit clicks the toggle five times on major routes.
- Assert icon changes and no spinner remains visible.
- Assert theme persists after reload.
- Assert no hydration warning is logged.

## BUG-DATA-SKILL-AUTOCOMPLETE-SPARSE

Observed UI text:
- Typing `S` shows too few suggestions, for example only `SQL`.

Affected route:
- Profile, onboarding, and any skill editor/autocomplete surface.

Suspected subsystem:
- Skill suggestion endpoint, frontend autocomplete component, seed skill data, skill taxonomy, alias normalization, search ranking.

Expected behavior:
- Skill autocomplete should provide multiple realistic, relevant suggestions across technical, tool, language, soft-skill, domain, certification, and knowledge categories.
- Queries such as `s`, `machine`, `data`, `python`, `docker`, `kubernetes`, `ml`, `ai`, `statistics`, `credit`, `airflow`, `terraform`, `english`, `komunikasi`, and `analisis` should return useful results quickly.
- Duplicate selected skills should not be added twice.

Actual behavior:
- User manually observed a sparse suggestion set, indicating the taxonomy may be tiny or hardcoded.

Reproduction steps:
- Open profile, onboarding, or a skill editor route.
- Type the target queries into the skills autocomplete.
- Observe dropdown contents, latency, loading state, selected-skill behavior, and duplicates.

Evidence still needed:
- API responses for each query.
- Dropdown screenshots and DOM snapshots.
- Latency per query.
- Current skill data source and taxonomy size.
- Duplicate/alias behavior evidence.

Test plan:
- Semantic Selenium audit runs the listed queries and captures suggestions.
- Backend/API probe checks the skill search endpoint directly if available.
- Classify sparse results as data/taxonomy issue, endpoint ranking issue, or frontend rendering issue.

## BUG-DATA-JOB-DESCRIPTION-SHALLOW

Observed UI text:
- Job detail descriptions appear as a one-line description rather than rich job-posting content.

Affected route:
- `/jobs/{sample_id}`.

Suspected subsystem:
- Scraper detail-page fetching, parser/normalizer, database schema/storage, gateway job detail endpoint, frontend job detail rendering.

Expected behavior:
- Job detail pages should display full job detail content when legally and technically available.
- Supported structured sections should include description, responsibilities, requirements, nice-to-have, seniority level, employment type, job function, industry, source, and related metadata when present.
- Missing fields should degrade cleanly without breaking layout.

Actual behavior:
- User manually observed shallow one-line descriptions.
- If API data is shallow, this is a data pipeline/storage issue rather than only a frontend rendering issue.

Reproduction steps:
- Fetch jobs from the API.
- Open at least five `/jobs/{sample_id}` pages from real returned API data.
- Compare visible description depth with API payload fields and any stored source data.

Evidence still needed:
- API payload samples for five job detail records.
- Screenshots and DOM snapshots of job detail pages.
- Database stored job fields for the sampled records.
- Parser/scraper evidence showing whether detail pages are fetched and full text is preserved.

Test plan:
- Semantic Selenium audit opens at least five job details.
- Assert description is not only a one-line generated summary when source data provides richer content.
- Assert structured fields render when present and the UI works when fields are missing.
- Classify root cause as frontend display, API contract, storage schema, parser, or upstream data availability.

## BUG-DATA-SKILL-GAP-LOW-CONTEXT

Observed UI text:
- No explicit text; user reported job detail content is too shallow for meaningful skill extraction and skill gap.

Affected route:
- `/jobs/{sample_id}`, skill-gap displays, and recommendation explanation surfaces.

Suspected subsystem:
- Job description ingestion, skill extraction, required/preferred skill storage, skill-gap API, SBERT/recommendation reason input quality.

Expected behavior:
- Skill gap should use required, preferred, and extracted skills from rich job detail text rather than only a short card summary.
- Recommendation reasons and SBERT matching should receive meaningful text context.

Actual behavior:
- Shallow job descriptions likely reduce extracted skill quality and make skill-gap/reason output low-context.

Reproduction steps:
- Open sampled job detail pages.
- Inspect visible skill gap and required/preferred skills.
- Compare skill-gap output with API/database fields and raw description text if present.

Evidence still needed:
- Skill-gap API response for sampled jobs.
- Extracted/required/preferred skills in job detail payloads.
- Underlying stored description text and parser output.
- Before/after parser fixture evidence using the user-provided CBI Data Scientist description when available.

Test plan:
- Semantic Selenium audit verifies skill gap on sampled job detail pages.
- Backend parser/unit tests later verify extraction from a rich fixture.
- If data is shallow, create a data pipeline bug entry before implementing schema/parser/storage changes.
