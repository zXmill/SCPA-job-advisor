# Plan — 24h Link / Application-Status Checker (deferred action #5)

**Risk tier: FULL.** Touches DB schema, external scraping at scale, and (Phase 2)
the retrieval + public-listing visibility gate. No auth/money, but outward-facing
(hits live job boards) and defended-number-adjacent (changes what counts as a
shown job). Adversarial review (plan-reviewer) run below; findings folded as C#.

Source of truth for the design intent: memory `code-review-deferred-actions.md` #5.
This plan **corrects** three stale assumptions in that memory (see receipts D1/D2/D3).

---

## 1. Verification — claims checked against live code (file:line)

| Claim (from memory / brief) | Reality in code | Verdict |
|---|---|---|
| "migration 017" adds the columns | `017_profile_onboarding_fields.py` **already exists**; latest migration | STALE → use **018** |
| add `application_status` column | `ApplicationStatus` enum + `applications.status` already exist (`db/models.py:127,484`) | COLLISION → drop it; single `link_status` (user decision Q2) |
| "reuse scraper httpx+ld+json" | Scraper `/scrape/run` is **seed-list oriented**, not single-URL (`stage_1_scrape.py:270`); JSON-LD `JobPosting` parse lives at `services/scraper/main.py:1345-1392`, extracts **no** `validThrough`/expiry | Port parse into worker (user decision Q3); add expiry extraction |
| flipping visibility = set `is_active=false` | `is_active=false` hides from **recommendations** (`stage_retrieval.py:116`) **and** public listing (`gateway/main.py:4225`); admin counts read it (`gateway/main.py:3185`) | High blast radius |
| checker can own `is_active` | Both upserts write `is_active = EXCLUDED.is_active` (default `True`): `stage_1_scrape.py:641`, `gateway/main.py:790` → **a re-scrape resurrects a checker-closed job** | Confirmed conflict → checker must NOT touch `is_active` (user decision Q1) |
| worker + compose pattern exists | `continuous_scraper.py` (bounded/run-forever, env config, grace/backoff, report writer, signal handlers) + compose `scraper-worker` (`docker-compose.yml:106-140`) | Direct template |
| schema via migration | Tests build schema via `Base.metadata.create_all` (`tests/conftest.py:5-7`), **not** alembic | Schema change lands in **two** places: `db/models.py` Job ORM **and** alembic `018` — must match (C-note) |
| DB access | `create_async_engine` on `PIPELINE_DATABASE_URL`/`DATABASE_URL`/`GATEWAY_DATABASE_URL`; reuse `stage_1_scrape._database_url()` | OK |
| precedent for soft-deactivation | `_CATALOG_DEDUP_SWEEP_SQL` sets `is_active=false` + annotates `match_data` (`stage_1_scrape.py:490-516`) | Pattern precedent (we use `link_status` instead) |

Migrations are **Alembic** (`op.add_column`, `revision`/`down_revision` chain);
`018` revises `017_profile_onboarding_fields`.

## 2. Decisions with receipts

| # | Decision | Source |
|---|---|---|
| D1 | Migration number is **018**, revises 017 | my judgment — 017 already exists (`db/migrations/017_*.py`) |
| D2 | **Single** `link_status` column (open/closed/expired/unreachable) + `last_checked_at`, `consecutive_check_failures`, `last_http_status`; **no** `application_status` | User Q2 = "Single link_status + bookkeeping" |
| D3 | Checker **never writes `is_active`**; visibility via a new `link_status` gate clause | User Q1 = "New link_status column + gate" |
| D4 | Per-URL fetch + JSON-LD parse is **self-contained** in the worker; scraper service untouched | User Q3 = "Self-contained in checker worker" |
| D5 | Gate excludes only `link_status IN ('closed','expired')`. Short-term `unreachable` is **not** hidden (transient board outage must not hide live jobs); **persistent** unreachable escalates per D13 | my judgment — matches the memory's "grace window before deactivate" intent; avoids false-negative hiding |
| D6 | Grace window: `consecutive_check_failures >= 3` before flipping to closed/unreachable; any success resets counter to 0 and sets `open` | Memory #5: "grace window (≥3 consec failures) before is_active=false" |
| D7 | Hard-dead HTTP (`404`/`410`) and past `validThrough` still require the grace window (no fast-path), to stay robust against soft-404 pages that 200 | my judgment — uniform state machine is simpler + safe; revisit only if 24h latency to hide is too slow |
| D8 | Upsert hot path does **not** touch `link_status`; the checker is its sole writer. A re-scrape therefore preserves a `closed` verdict (INSERT omits the column → server_default only on first insert; `ON CONFLICT DO UPDATE` leaves it untouched) | my judgment — honors INV-2; ≤24h staleness bounded by checker cadence |
| D9 | Split into **two phases**: P1 = schema + worker (write-only, nothing hides); P2 = visibility gate. Lets the defended-number-adjacent switch land as its own verify-loop + rollback unit | plan-phase guidance "size to sessions / foundation-first" |
| D10 | Self-loop compose service mirroring `scraper-worker` (sleep-based ~24h cadence), not OS cron | my judgment — consistent with existing `scraper-worker`; memory said "compose service" |
| D11 | Checker **reuses the scraper's SSRF fetch guard** (`_validate_scrape_url`/`_is_unsafe_address`/host-suffix allowlist, `scraper/main.py:105-176`), not just the JSON-LD parser. DB `source_url` is untrusted input | C1 (plan-reviewer, CRITICAL) |
| D12 | `GET /api/jobs/{id}` (`gateway/main.py:4924-4937`) **stays resolvable** for closed/expired (mirrors "deactivated rows stay resolvable by id", `stage_1_scrape.py:488`); P2 adds `link_status` to the detail payload so the UI badges "closed" + disables Apply. Not a 404 | C3 (HIGH) |
| D13 | Persistent unreachability escalates to hidden: `link_status='unreachable'` **and** `consecutive_check_failures >= LINK_UNREACHABLE_HIDE_FAILURES` (default 7 ≈ 7 days at 24h cadence) is added to the P2 gate exclusion. Counter-based, not `last_checked_at` age (the checker refreshes `last_checked_at` every cycle incl. failures, so age never escalates) | C4 (MEDIUM) |
| D14 | Accept ≤24h false-hide when a `closed` URL is re-listed live (checker re-opens next scan). Scraper must **not** write `link_status` (would reintroduce the resurrection class INV-1 forbids) | C5 (MEDIUM) |
| D15 | Politeness: **per-host** concurrency cap + inter-request delay; sweep spread so the full active catalog is covered ~once/24h; `429`/rate-limit = back-off-next-cycle, **never** a same-cycle `consecutive_check_failures` increment | C6 (MEDIUM) |

## 3. Invariants (must not break — asserted in §Gates)

- **INV-1** `is_active` is never written by the checker. (grep proof + is_active-gated tests unchanged.)
- **INV-2** Scraper/gateway **upsert hot path unchanged** (single-producer hash + outbox contract intact). New column has a server_default so existing explicit-column INSERTs still succeed.
- **INV-3** Migration 018 is reversible (`downgrade` drops all 4 columns cleanly).
- **INV-4** `db/models.py` Job ORM and alembic 018 define the **same** columns (test DB == prod DB).
- **INV-5** Checker is a fully isolated process: any fetch/parse/DB error is logged, never raised into a request path; it cannot degrade recommendations or listing.
- **INV-6** Politeness: bounded concurrency, per-request timeout, existing scraper User-Agent norms, per-cycle batch cap. No unbounded fan-out at the boards.
- **INV-7** Model-layer contracts untouched (`ml-model-contract-locks`). Phase 1 changes **no** user-visible output and **no** defended number.
- **INV-8** **SSRF**: every outbound fetch validates scheme + host-suffix allowlist + resolved IP (block private/link-local/`169.254.169.254` metadata) before connecting; redirects re-validated each hop and hop-capped. `source_url` is treated as untrusted. (C1/C2)
- **INV-9** Per-host politeness: per-host concurrency + inter-request delay; `429`/rate-limit never increments `consecutive_check_failures`. (C6)

## 4. Adversarial review — folded findings

Ran `plan-reviewer` against live code. Architecture verified **sound** — D1/D2/D3/D8/INV-1 confirmed at line level (resurrection-avoidance reasoning holds; upsert omits `link_status` at `stage_1_scrape.py:616-646`, `gateway/main.py:745-791`). All 9 findings are **omission** class; folded below.

| C# | Finding (severity) | Resolution in this plan |
|---|---|---|
| C1 | **SSRF** — worker fetches DB-controlled `source_url` with no host/IP guard; "port only the JSON-LD parse" scope dropped the scraper's `_validate_scrape_url`/`_is_unsafe_address` defense (`scraper/main.py:105-176`). Metadata/internal-IP fetch by a process holding `DATABASE_URL`. (CRITICAL) | D11 + INV-8. P1 ports the **fetch guard**, not just the parser; P1 gate adds a private-IP/non-allowlisted-host test asserting no fetch. |
| C2 | **Redirects** — httpx redirect policy unspecified; `follow_redirects=True` re-opens SSRF and marks 301→200 "expired" pages `open`. (HIGH) | INV-8. P1 pins explicit redirect handling, caps hops, re-validates each hop; fixtures 301→expired ⇒ closed, 301→cross-host ⇒ blocked. |
| C3 | **Ungated detail** — `GET /api/jobs/{id}` (`gateway/main.py:4924-4937`) has no active/link_status gate, absent from P2 audit; deep-link to a closed job renders live w/ dead Apply. (HIGH) | D12. P2 keeps it resolvable (mirrors `stage_1:488`) + adds `link_status` to the payload for a "closed" badge; test asserts chosen behavior. |
| C4 | **Permanent unreachable** stays visible forever (D5 never hides `unreachable`); dead domain = permanent visible dead link. (MEDIUM) | D13. Persistent unreachable (≥7d) escalates into the P2 gate exclusion. |
| C5 | **Re-open latency** — a re-listed `closed` URL stays hidden ≤24h until next scan (false-hide). (MEDIUM) | D14. Accepted + documented; scraper must not write `link_status`. |
| C6 | **Politeness** — full-catalog 24h sweep, no per-host throttle/robots, concentrated on few boards ⇒ 429/ban ⇒ mass-`unreachable`. (MEDIUM) | D15 + INV-9. Per-host cap + delay, spread sweep, 429 = backoff not failure. |
| C7 | **Closed-marker accuracy** unspecified + validated on zero real data; ported parser reads no `validThrough`/markers. (MEDIUM) | P1 captures real dead-posting fixtures via scraper `/scrape/url` per board + enumerates the marker set; P2 done-criteria adds a precision spot-check, not just "tests green". |
| C8 | **INV-4 hole** — tests build schema via `create_all` (`conftest.py:6`), so a wrong `018` passes the whole suite; only prod `alembic upgrade` bites. (MEDIUM) | P1 gate adds an autogenerate-diff check: after `alembic upgrade head`, `alembic revision --autogenerate` must yield an **empty** diff vs the ORM. |
| C9 | **server_default** must be set in `018` at DB level (not only ORM), else explicit-column INSERTs fail in prod while passing tests. (LOW) | `018` uses `server_default=sa.text("'open'")`/`sa.text("0")` (017 idiom); covered by C8's diff gate. |

---

## Phase 1 — Schema + checker worker (write-only, no visibility change)

**Intent.** Add the `link_status` + bookkeeping columns (ORM **and** alembic 018),
and a `services/pipeline/link_status_checker.py` worker that re-checks each active
job's `source_url` on a ~24h cadence and records a verdict — **without changing any
retrieval or listing SQL**. Feature is observably inert to end users after P1.

**Shape (executor re-derives specifics against live code):**
- `db/models.py` `Job`: add `link_status` (String/short, server_default `'open'`,
  nullable-safe), `last_checked_at` (DateTime, null), `consecutive_check_failures`
  (Integer, server_default `0`), `last_http_status` (Integer, null). Add an index on
  `link_status` (partial, for the P2 gate + checker scan).
- `db/migrations/018_link_status_checker.py`: mirror those adds with DB-level
  `server_default=sa.text("'open'")` / `sa.text("0")` on the NOT-NULL cols (017 idiom, C9);
  `downgrade` drops all 4.
- `services/pipeline/link_status_checker.py`: mirror `continuous_scraper.py` structure —
  frozen `@dataclass` config `from_env()`, bounded default / `--run-forever`, signal
  handlers, report writer, `asyncio` loop. Core: select active jobs with non-empty
  `source_url` ordered by `last_checked_at ASC NULLS FIRST`, batch-capped; **per-host**
  semaphore + inter-request delay (D15/INV-9); classify; apply the D6/D7 grace-window
  state machine; UPDATE `link_status`/`last_checked_at`/`consecutive_check_failures`/
  `last_http_status` only. Never writes `is_active`.
- **Fetch safety (C1/C2/INV-8):** every GET goes through the scraper's SSRF guard — reuse
  `services.scraper.main._validate_scrape_url`/`_is_unsafe_address`/host-suffix allowlist
  (do **not** re-implement); `source_url` is untrusted. Explicit `follow_redirects` with a
  hop cap, re-validating host + resolved IP on **each** hop; a redirect into a known
  "expired" path is a closed signal.
- Parser: port the JSON-LD `JobPosting` block (`scraper/main.py:1345-1392`) and **add**
  `validThrough` extraction + an enumerated per-board closed-marker set (seeded from real
  fixtures, C7). No `validThrough`/marker logic exists today.
- Classification → status: `open` (200 + not expired/closed), `expired` (validThrough past),
  `closed` (404/410 or a matched closed-marker), `unreachable` (timeout/5xx/DNS).
  **`429` = back-off next cycle, never a failure increment** (D15). Grace window gates every
  non-open transition (D6/D7); `consecutive_check_failures` feeds the D13 persistent-unreachable
  escalation used by P2.
- `docker-compose.yml`: add `link-status-checker` service (build `services/pipeline/Dockerfile`,
  `command: python -m services.pipeline.link_status_checker --run-forever`), env mirroring
  `scraper-worker` (DATABASE_URL, interval, batch cap, concurrency), `depends_on: postgres healthy`.
- Tests (`tests/test_link_status_checker.py`): unit-test the pure classifier + grace-window
  state machine with fixture HTML/JSON-LD and a mocked httpx (no network); assert (a) a
  private-IP / non-allowlisted `source_url` is **never fetched** (C1), (b) a cross-host
  redirect is blocked and a 301→expired-page ⇒ `closed` (C2), (c) `429` does **not**
  increment `consecutive_check_failures` (C6); one `@pytest.mark.db` test that the worker
  updates the 4 columns and leaves `is_active` untouched.

**Gate (runnable — expected output):**
```
# schema round-trips
alembic upgrade head                 # -> "Running upgrade 017_... -> 018_link_status_checker"
alembic downgrade -1 && alembic upgrade head   # clean down+up, no error
# ORM == migration (INV-4/C8): autogenerate must see NO pending delta
alembic revision --autogenerate -m _probe   # -> empty upgrade()/downgrade(); then delete the probe file
pytest -m "not db"                   # fast suite green (baseline: 339 pass / 3 pre-existing SBERT-env fails)
pytest -m db tests/test_link_status_checker.py   # worker tests incl. SSRF/redirect/429 (C1/C2/C6), needs db_scpa_test
# INV-1 proof: no is_active writes in the checker
grep -n "is_active" services/pipeline/link_status_checker.py   # -> no UPDATE/INSERT of is_active
python -m services.pipeline.link_status_checker --help         # worker entrypoint imports + parses args
```
Cannot catch: real board responses (network). Covered by fixtures; live fetch is manual/P2-adjacent.

**Rollback:** remove the compose service + `link_status_checker.py`; `alembic downgrade -1`.
No retrieval/listing SQL touched, so nothing user-visible to revert.

**Done-criteria:** all P1 gate commands green; INV-1..INV-9 hold; C1/C2/C6/C8/C9 tests present + green; no visible/thesis change.

`/kickoff-phase docs/agent/LINK_STATUS_CHECKER_PLAN.md "Phase 1"`

---

## Phase 2 — Visibility gate (hide closed/expired jobs)

**Intent.** Flip the switch: exclude `link_status IN ('closed','expired')` from the
recommendation candidate pool and the public listing. Thin, isolated, independently
reversible. This is the defended-number-adjacent change → honesty note + ledger.

**Shape:**
- Visibility predicate (both surfaces): `link_status IS NULL OR (link_status NOT IN ('closed','expired') AND NOT (link_status = 'unreachable' AND consecutive_check_failures >= 7))` — the `('closed','expired')` exclusion **plus** the D13 persistent-unreachable escalation. Add beside `j.is_active = true` in `stage_retrieval.py` RETRIEVAL_SQL (line 116).
- `gateway/main.py` `/api/jobs` conditions (line ~4225) + any sibling active-gated job reads that back user-facing listing (audit lines 2942/2959/5017; **do not** change admin counts 3185-3186 — they should still see everything). Executor confirms each against live code.
- `gateway/main.py` `get_job` detail (`4924-4937`): **stays resolvable** for closed/expired (D12) but add `link_status` to `JOB_SELECT_COLUMNS`/detail payload so the frontend badges "closed"/"expired" + disables the Apply CTA. Do **not** 404 — deep links + saved/applied refs must still render.
- Tests: assert `closed`/`expired` **and** persistent-unreachable (fails≥7) jobs are excluded from `/api/jobs` + retrieval, while `open`/NULL/short-unreachable remain; `is_active` semantics unchanged; detail-by-id still resolves a closed job **and** exposes `link_status` (C3).
- Docs: `docs/architecture/MODEL_CONTRACTS.md` runtime table (new gate), `docs/agent/VALIDATION_LEDGER.md` entry, `docs/agent/ARTIFACT_INDEX.md` if needed; honesty note that shown-job counts now exclude confirmed-dead links (forward-only; does not retro-edit defended snapshots).

**Gate (runnable):**
```
pytest -m db tests/test_link_status_gate.py    # closed/expired + persistent-unreachable excluded; open/null/short-unreachable kept; detail-by-id resolves + exposes link_status (C3)
pytest -m "not db"                              # still green
pytest -m db                                    # full db suite green (no regression in jobs/filters/upsert tests)
```
Cannot catch: whether real boards' closed-markers match our parser (tuned via P1 fixtures + spot checks).

**Rollback:** revert the visibility predicate clause on both surfaces (the column + data stay, harmless). One-commit revert.

**Done-criteria:** gate tests green; full suite green; a real-fixture **precision spot-check** on closed-marker detection recorded (C7); docs + honesty note landed.

`/kickoff-phase docs/agent/LINK_STATUS_CHECKER_PLAN.md "Phase 2"`

---

## Progress tracker
- [ ] Phase 1 — schema + checker worker (write-only)
- [ ] Phase 2 — visibility gate + docs/honesty note

## Out of scope
- Per-user application lifecycle (`applications.status`) — unrelated to posting liveness.
- Notifying users their saved/applied job went dead (future phase).
- Headless rendering (boards are server-rendered + JSON-LD, per memory #5).
- Board official APIs / auth'd endpoints.
- Retro-editing already-defended thesis counts.

## Known-untestable (without network)
- Live board HTML/closed-marker drift → mitigated by fixture-driven parser tests + periodic spot checks; classifier + state machine are fully unit-tested offline.
