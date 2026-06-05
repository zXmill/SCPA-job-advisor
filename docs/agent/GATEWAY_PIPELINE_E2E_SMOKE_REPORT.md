# Gateway + Pipeline E2E Smoke Report — Scoped DQN Session Reranker
- **Branch**: `integration/dqn-session-reranker`
- **Latest scoped commit**: `05d6cc4 fix: align DQN session reranker canonical contract`
- **Scope**: gateway + pipeline + DQN runtime contract smoke only; full integration is not claimed
- **Repo state**: unrelated dirty/untracked files remain; no unrelated files were touched

## Git State
- branch: `integration/dqn-session-reranker`
- latest commit: `05d6cc4`
- staged changes: none
- unrelated dirty/untracked files present: yes

## Runtime Services
- dqn: healthy, rebuilt, up
- gateway: healthy, up
- pipeline: healthy, up
- sbert: healthy, up
- ncf: healthy, up
- postgres: healthy, up

## Health
- Gateway health: `200 healthy`
- Pipeline health: not_run_no_host_port (pipeline port not exposed to host; direct health not run from host)
- DQN health inside container: `200 healthy`

## DQN /rerank Runtime Reconfirmation
- Payload with candidates and session_events:
  - STATUS: 200
  - POLICY_OBJECTIVE: session_rerank
  - RANKED_JOBS_LEN: 2
  - HAS_TOP_LEVEL_FINAL_SCORE: False
  - HAS_JOB_FINAL_SCORE: False
- Empty candidates payload:
  - STATUS: 200
  - RANKED_JOBS_LEN: 0
  - POLICY_OBJECTIVE: session_rerank

## Pipeline Direct Smoke
- pipeline_direct_smoke: not_run_no_exposed_pipeline_endpoint
- No direct `pipeline/run` or `/api/pipeline` entrypoint was found from source search (`grep -RIn "pipeline/run|run_pipeline|/api/pipeline|stage_4_dqn_rank|stage_5_aggregate" services/gateway services/pipeline` returned no matches).
- Evidence gap: pipeline stage execution was not driven through an exposed pipeline HTTP route during this smoke.

## Focused Pipeline Tests
- Command: `.venv/Scripts/python -m pytest tests/test_pipeline_ta_contracts.py -q`
- Result: `2 failed, 4 passed, 1 warning`
- Blockers:
  - `test_stage_4_dqn_session_adapter_preserves_rank_trace`: source emits `session_rerank`; test asserts legacy `session_reranker`
  - `test_stage_5_active_session_reports_alpha_beta_gamma_formula`: test expects `(0.45, 0.35, 0.2)`; active function result is `(0.6, 0.4, 0.0)`
- Classification: `failed_contract`

## Focused Stage 4 Test
- Command: `.venv/Scripts/python -m pytest tests/test_dqn_policy_contracts.py::test_pipeline_dqn_stage_preserves_session_rerank_metadata -q`
- Result: `1 passed`

## Auth Discovery
- Auth helper scripts found: yes (`scripts/_smoke_auth_realdb.py`, `scripts/_check_auth_db.py`, `scripts/_probe_user.py`, `scripts/_probe_user_full.py`)
- Real env present: yes (`.env` found)
- Controlled auth smoke attempted in this pass: not_run_no_auth_token_fixture_used
- Result:
  - authenticated gateway recommendations smoke: not_run_no_auth_token
  - authenticated gateway `/api/learning-path` 410 smoke: not_run_no_auth_token

## Gateway Unauthenticated Route Smoke
- `POST /api/learning-path` unauthenticated:
  - STATUS: 401
  - detail: Missing authorization header

## Static Active Legacy Output Check
- Query: `grep -RIn --exclude-dir=.next --exclude-dir=node_modules --exclude-dir=.git -E "getLearningPath|learningPath|careerPath|skillPath|/api/learning-path|/learning-path|policy_objective.*skill_path|policy_objective.*session_reranker|dqn_final_score" services frontend/src tests | head -200`
- Match result: no output / no active frontend caller found
- Classification: `no active frontend caller found in queried source paths`

## Blockers
- `tests/test_pipeline_ta_contracts.py` had two contract failures that were reproduced and then patched in this pass:
  - `test_stage_4_dqn_session_adapter_preserves_rank_trace`: source emits `session_rerank`; test asserted legacy `session_reranker`
  - `test_stage_5_active_session_reports_alpha_beta_gamma_formula`: test input used legacy `dqn_mode = "session_reranker"`, causing Stage 5 to treat DQN as unavailable
- Pipeline direct HTTP smoke was not_run_no_exposed_pipeline_endpoint
- Auth-required gateway smoke was not_run_no_auth_token

## Pipeline TA Contract Follow-up
- File patched: `tests/test_pipeline_ta_contracts.py`
- Change summary:
  - fake Stage 4 DQN response `dqn_mode` updated from `session_reranker` to `session_rerank`
  - Stage 4 result assertion updated to expect `session_rerank`
  - Stage 5 active-session test input `dqn_mode` updated from `session_reranker` to `session_rerank`
- Validation:
  - `.venv/Scripts/python -m pytest tests/test_pipeline_ta_contracts.py -q` → `6 passed, 1 warning`
  - `.venv/Scripts/python -m pytest tests/test_dqn_policy_contracts.py tests/test_dqn_learning_path.py tests/test_market_aware_skill_path.py tests/test_pipeline_ta_contracts.py -q` → `20 passed, 1 warning`
- Root cause: test contract used legacy `session_reranker`; canonical source/runtime uses `session_rerank`. After aligning test input, Stage 5 correctly treated DQN as available and returned expected active-session weights `(0.45, 0.35, 0.2)`.

## Final Status
Gateway + Pipeline E2E smoke partially passed. Authenticated gateway checks and direct pipeline HTTP smoke were skipped and documented. Pipeline TA contract tests now align with canonical `session_rerank`.
