# DQN Session Reranker Merge Report — Evidence Finalization
- **Branch**: `integration/dqn-session-reranker`
- **Base**: `codex/p1-pipeline-evidence-contract`
- **Agent worktree**: `E:/TUGAS AKHIR/SCPA-agent2-dqn-tests` (`codex/dqn-session-reranker-tests`, untouched)
- **Scope**: scoped canonical patch validation only; full integration not claimed

## Validation State
Scoped canonical patch validated. The branch is not committed yet because the repository contains unrelated dirty and untracked files outside the scoped patch set. No files were added, and no P0-defect resolution is claimed here beyond the scoped contract validation.

## py_compile Result
- Files checked:
  - `services/dqn/main.py`
  - `services/gateway/main.py`
  - `services/pipeline/stages/stage_4_dqn_rank.py`
  - `services/pipeline/stages/stage_5_aggregate.py`
- Result: `PY_COMPILE_OK`

## pytest Result
Scoped subset rerun with real output:

- Command: `pytest tests/test_dqn_policy_contracts.py tests/test_dqn_learning_path.py tests/test_market_aware_skill_path.py -q`
- Result: 14 passed, 0 failed, 1 warning
- Warning source: PyPDF2 deprecation warning in shared import chain
- Duration context: ~10s runtime

This result reflects the genuinely observed test count after canonical contract updates. An earlier partial report claimed 16 passed; that count was incorrect and has been replaced by this validated run.

## Static Grep and Classifications
Scoped grep targets:
- `services/dqn/main.py`
- `services/gateway/main.py`
- `services/pipeline/stages/stage_4_dqn_rank.py`
- `services/pipeline/stages/stage_5_aggregate.py`
- `tests/test_dqn_policy_contracts.py`
- `tests/test_dqn_learning_path.py`
- `tests/test_market_aware_skill_path.py`

Search terms:
- `session_reranker`
- `session_history`
- `final_score`
- `learning_path`
- `learning-path`
- `career_path`
- `skill_path`
- `market_demand`
- `skill_gap_reduction`
- `estimated_skill_gap_after`

Findings and classifications:

- Match: `session_reranker` in `services/dqn/main.py`
  - Classification: internal implementation artifact only
  - Status: allowed_internal_alias
- Match: `session_history` in `services/dqn/main.py`
  - Classification: backward-compatible runtime alias used for routing from gateway to internal helpers
  - Status: allowed_internal_alias
- Match: `final_score` inside the DQN branch in `services/dqn/main.py`
  - Classification: internal intermediate score excluded from active rerank response
  - Status: allowed_internal_alias
- Match: `final_score` in `services/gateway/main.py`
  - Classification: gateway still reads upstream Stage 5 or upstream fields from candidates
  - Status: allowed_internal_alias
- Match: `_session_history_for_user` in `services/gateway/main.py`
  - Classification: internal helper naming; no canonical contract violation observed there
  - Status: allowed_internal_alias
- Match: `learning_path` and `/learning-path` in `services/gqn/main.py` and `services/gateway/main.py`
  - Classification: legacy compatibility route with auth-guard behavior
  - Status: allowed_deprecated
- Match: `session_reranker` in `services/pipeline/stages/stage_4_dqn_rank.py`
  - Classification: backward-compatible mode compatibility path
  - Status: allowed_internal_alias
- Match: `session_history` in `services/pipeline/stages/stage_4_dqn_rank.py`
  - Classification: accepted fallback key alongside `session_events`
  - Status: allowed_internal_alias
- Match: `dqn_final_score` in `services/pipeline/stages/stage_4_dqn_rank.py`
  - Classification: legacy mapping label referring to `final_score`
  - Status: allowed_internal_alias
- Match: `final_score` in `services/pipeline/stages/stage_5_aggregate.py`
  - Classification: Stage 5 is the canonical owner for `final_score`
  - Status: allowed_stage5_final_score
- Match: `session_reranker` and `session_history` in tests
  - Classification: test fixtures and assertions refer to legacy compatibility wording
  - Status: allowed_test_guard
- No matches were interpreted as active runtime blockers under the current scoped inspection.

## Frontend and Backend Active Legacy Call Check
Active call sites:

- `frontend/.next/dev/server/chunks/ssr/src_0-1vg-o._.js` references:
  - `learningPath`
  - `data.learningPath`
  - `pathRes.value.steps`
- `frontend/.next/dev/static/chunks/src_lib_0jie57m._.js` references:
  - `this.request('/api/learning-path', { method: 'POST' })`
- Matching compiled bundle artifacts repeat the same patterns across several Next.js-built chunks.

Classification:

- `data.learningPath`: allowed_documentation
- `this.request('/api/learning-path')`: allowed_deprecated_route
- `pathRes.value.steps`: allowed_documentation
- No confirmed `careerPath` or `skillPath` active call sites were found in the scoped search.
- Use caution: these references come from compiled bundles. Source-level search for `frontend/src` did not return TypeScript/TSX matches under the narrow search conditions used, but the compiled output preserves the legacy endpoints.

## Git Status After Patch
- Current branch: `integration/dqn-session-reranker`
- Repo state: dirty with unrelated modified files and untracked files
- Scoped modified files among the targeted set:
  - `services/dqn/main.py`
  - `services/gateway/main.py`
  - `services/pipeline/stages/stage_4_dqn_rank.py`
  - `tests/test_dqn_learning_path.py`
- Many unrelated files are also present as modified or untracked and were not touched by this scoped patch.

## Commit Safety
Commit is intentionally deferred due to unrelated dirty and untracked files in the repository. The scoped canonical patch should not be bundled with unrelated state.

Suggested commit message if the branch is later prepared in isolation:
`fix: align DQN session reranker canonical contract`

## Final Statement
Scoped canonical contract validation passed. Commit is intentionally deferred due to unrelated dirty/untracked files.
