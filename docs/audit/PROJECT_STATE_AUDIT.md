# Project State Audit

Date: 2026-06-05

Scope: Phase 0 audit only. No runtime code was changed for this audit.

## Recovery Note

The repository is already dirty and contains a nested Git repository at `frontend/.git`. This audit treats the current filesystem as the source of truth and avoids modifying existing runtime files, test files, and `docs/agent/*` state files.

Required recovery commands were run before edits:

```powershell
git status --short
git branch --show-current
git log --oneline -5
Get-ChildItem -Path . -Force -Directory -Recurse -Depth 3 -Filter .git
```

Windows equivalent was used for the requested Unix `find . -maxdepth 3 -name ".git" -type d` command.

## Repository State

- Current branch: `agent-run`
- Latest commits:
  - `7425ae7 docs: record continuous scraping evidence`
  - `f26b208 feat: add continuous realtime scraper worker`
  - `b87238c docs: record realtime scrape quality evidence`
  - `f236820 fix: enforce realtime scrape quality gate`
  - `97127a9 docs: record product-quality data remediation evidence`
- Git repositories detected:
  - `E:\TUGAS AKHIR\SCPA\.git`
  - `E:\TUGAS AKHIR\SCPA\frontend\.git`

## Dirty Files

Tracked files already modified before this Phase 0/1 documentation task:

- `README.md`
- `docker-compose.yml`
- `docs/agent/ARTIFACT_INDEX.md`
- `docs/agent/PROJECT_STATE.md`
- `docs/agent/SESSION_REPORT.md`
- `docs/agent/TASK_QUEUE.json`
- `docs/agent/VALIDATION_LEDGER.md`
- `notebooks/01_indonesian_hybrid_dataset_eda.ipynb`
- `notebooks/02_hybrid_dataset_validation.ipynb`
- `reports/debug/continuous_scrape/cycles.ndjson`
- `reports/debug/continuous_scrape/summary.json`
- `scripts/run_full_pipeline.py`
- `services/gateway/main.py`
- `services/pipeline/continuous_scraper.py`
- `services/pipeline/main.py`
- `services/pipeline/stages/stage_1_scrape.py`
- `services/pipeline/stages/stage_2_encode.py`
- `services/pipeline/stages/stage_4_dqn_rank.py`
- `services/pipeline/stages/stage_5_aggregate.py`
- `services/scraper/main.py`
- `services/shared/skill_taxonomy.py`
- `tests/test_continuous_scraper.py`
- `tests/test_cv_upload.py`
- `tests/test_job_description_quality.py`
- `tests/test_job_upsert_idempotency.py`
- `tests/test_profile_completeness.py`
- `tests/test_sbert_job_embedding_cache.py`
- `tests/test_skill_gap_detail.py`
- `tests/test_skill_taxonomy_search.py`

Tracked deletion:

- `SCPAv2`

Major untracked areas present before this audit:

- Project docs: `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`, `docs/MODELS.md`, `docs/THESIS_WRITING_NOTES.md`, `docs/architecture/`, `docs/ml/`, `docs/evidence/`, and many other `docs/*` folders.
- Runtime and data files: `db/`, `services/dqn/`, `services/ncf/`, `services/sbert/`, `services/hybrid/`, `services/evaluation/`, `requirements*.txt`, `alembic.ini`, `data/sample/`, `models/`.
- Frontend nested repo: `frontend/`.
- Generated reports and screenshots: `reports/`, `browser_screenshots/`, `*.png`, notebooks, and thesis PDFs.
- Secrets folder: `secrets/` is untracked and must not be staged.

No unrelated dirty file was reverted or staged during this audit.

## Major Services Found

The current repo contains the following service boundaries:

- Gateway API: `services/gateway/main.py`
- Pipeline orchestrator: `services/pipeline/main.py`
- Pipeline stages: `services/pipeline/stages/stage_1_scrape.py`, `stage_2_encode.py`, `stage_3_ncf_score.py`, `stage_4_dqn_rank.py`, `stage_5_aggregate.py`
- Scraper: `services/scraper/main.py`
- SBERT: `services/sbert/main.py`, `services/sbert/embedder.py`, `services/sbert/training/*`
- NCF: `services/ncf/main.py`, `services/ncf/training/*`
- DQN: `services/dqn/main.py`, `services/dqn/training/*`
- Hybrid service: `services/hybrid/main.py`
- Evaluation: `services/evaluation/*`
- Shared helpers: `services/shared/*`
- Database schema and migrations: `db/*`
- Frontend: `frontend/` as a nested Git repository

## Current Runtime Architecture

Observed active recommendation flow:

1. `services/pipeline/main.py` imports and runs the staged pipeline.
2. `stage_2_encode.py` calls SBERT `/encode` and emits `sbert_score`, job embeddings, model metadata, and fallback flags.
3. `stage_3_ncf_score.py` calls NCF `/recommend/ncf` and emits `ncf_score`.
4. `stage_4_dqn_rank.py` calls DQN `/rank` and emits `dqn_score` plus DQN metadata.
5. `stage_5_aggregate.py` computes final ranking with dynamic weights, skill-alignment heuristics, and calibration.
6. `services/gateway/main.py` exposes `/api/recommendations` and maps pipeline output to frontend response fields.

Evidence:

- `services/pipeline/main.py:364` runs encode.
- `services/pipeline/main.py:371` runs NCF scoring.
- `services/pipeline/main.py:378` runs DQN rank.
- `services/pipeline/main.py:389` runs aggregation.
- `services/pipeline/stages/stage_2_encode.py` emits `sbert_score`.
- `services/pipeline/stages/stage_3_ncf_score.py` emits `ncf_score`.
- `services/pipeline/stages/stage_4_dqn_rank.py` emits `dqn_score`, `dqn_q_value`, and skill-path metadata.
- `services/pipeline/stages/stage_5_aggregate.py` emits `final_score`, `weights`, explanations, and ablation fields.
- `services/hybrid/main.py:1` labels the standalone hybrid service as stale and not active.

## Current Model Architecture

Current SBERT role:

- Implemented as profile-to-job semantic embedding/scoring.
- Has deterministic fallback mode, but current service documentation says fallback should not be silent when transformer mode is required.
- Current code produces similarity scores, but the active stage does not yet prove a Top-N candidate-generator contract with `semantic_rank`, Recall@50, or Recall@100.

Current NCF role:

- Implemented as an online NeuMF service with exposure-aware implicit feedback.
- Pipeline passes candidate IDs and profile/job context to `/recommend/ncf`.
- It can personalize after feedback, but the audited sample evidence is very small: 5 users, 9 jobs, 21 interactions in `reports/full_pipeline_summary.json`.

Current DQN role:

- DQN has an active `/rank` endpoint, but active runtime and tests still expose `policy_objective = "skill_path"` and learning-path reward fields.
- Gateway still exposes `/api/learning-path`, computes market demand, and calls DQN `/learning-path`.
- The DQN implementation currently mixes career/skill-path planning and job reranking.

Current hybrid role:

- Active blending is in `services/pipeline/stages/stage_5_aggregate.py`, not in the standalone `services/hybrid/main.py`.
- Current weights are:
  - cold: SBERT `0.75`, NCF `0.20`, DQN `0.05`
  - warm: SBERT `0.55`, NCF `0.35`, DQN `0.10`
  - active: SBERT `0.45`, NCF `0.40`, DQN `0.15`
- This does not match the revised architecture contract exactly.

## Obvious Mismatches With Thesis Architecture

### P0: DQN framing contradiction

The revised thesis contract says DQN is a session-based dynamic reranker and not a learning-path planner. Current code and tests still preserve learning-path behavior.

Evidence:

- `services/dqn/main.py:1128` exposes `/learning-path`.
- `services/dqn/main.py:694`, `services/dqn/main.py:998`, and `services/dqn/main.py:1024` emit `policy_objective = "skill_path"`.
- `services/dqn/training/train_dqn.py:88` writes `policy_objective = "skill_path"`.
- `tests/test_dqn_learning_path.py` directly tests DQN learning-path behavior.
- `tests/test_dqn_policy_contracts.py:86` and `tests/test_dqn_policy_contracts.py:215` assert `skill_path`.
- `services/gateway/main.py:3290` exposes `/api/learning-path`.

### P0: DQN output lacks session-reranker provenance

The revised contract requires `dqn_mode = "session_reranker"`, candidate-pool provenance, rank movement, session interaction count, and reward trace. Current DQN output does not consistently provide those fields.

Evidence:

- Repository-wide search found `session_reranker` mostly in review docs and artifacts, not active runtime output.
- `stage_4_dqn_rank.py` preserves `dqn_q_value`, but not `dqn_mode`, `candidate_pool_source`, `rank_before_dqn`, `rank_after_dqn`, or `reward_trace`.

### P1: Hybrid weights are inconsistent with contract

The revised contract defines cold-start as pure SBERT and disables DQN when there is no session signal. Current active aggregator always gives DQN at least `0.05`.

Evidence:

- `services/pipeline/stages/stage_5_aggregate.py` defines `dynamic_weights()`.
- `docs/architecture/01-system-architecture.md` and `docs/ARCHITECTURE.md` still describe older or different weights.

### P1: SBERT candidate-generation evidence is incomplete

SBERT is implemented as a scorer, but evidence for semantic candidate generation needs Recall@20, Recall@50, Recall@100, NDCG@10, NDCG@50, MRR@10, MAP@100, similarity distribution, and error analysis.

Evidence:

- `CODE_REVIEW_SBERT_V2_RETRIEVAL_ALIGNMENT.md` already flags missing retrieval-level evidence.
- `docs/MODELS.md` records triplet accuracy, NDCG@5, and Recall@5, but not the revised Top-N evidence set.

### P1: NCF evidence must be labeled as limited

NCF exists and uses feedback, but the current report evidence is sample-scale and must not be overclaimed.

Evidence:

- `reports/full_pipeline_summary.json` records 5 users, 9 sample jobs, 21 interactions.
- `reports/evaluation_metrics_summary.json` records existing artifacts and sample dataset counts.

### P1: Explanation terms leak old DQN framing

The explanation layer should show individual matched skills and missing skills. Current explanations and gateway provenance still use DQN skill-path language.

Evidence:

- `services/pipeline/stages/stage_5_aggregate.py` appends `DQN career-action signal`.
- `services/gateway/main.py:3438` emits `skill_path_signal` in explanation provenance.
- `reports/full_pipeline_summary.json` includes `DQN next career milestone`.

## Files Containing Learning-Path, Career-Path, or Skill-Path Terminology

Representative active/runtime files:

- `services/dqn/main.py`
- `services/dqn/training/train_dqn.py`
- `services/pipeline/stages/stage_4_dqn_rank.py`
- `services/gateway/main.py`
- `tests/test_dqn_learning_path.py`
- `tests/test_dqn_policy_contracts.py`
- `tests/test_market_aware_skill_path.py`

Representative docs and reports:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/MODELS.md`
- `docs/DATASET.md`
- `docs/DEMO_GUIDE.md`
- `docs/THESIS_WRITING_NOTES.md`
- `docs/architecture/01-system-architecture.md`
- `docs/ml/DQN_SKILL_PATH_RECOMMENDER.md`
- `docs/ml/MARKET_AWARE_SKILL_PATH.md`
- `docs/debugging/04-debugging-dqn-service.md`
- `reports/full_pipeline_summary.json`
- `reports/thesis_evaluation_summary.md`
- `CODE_REVIEW_DQN_V2_ALIGNMENT.md`

## Files Containing Module, Quiz, or Dropout Terminology

The raw audit term `module` is noisy and appears in tooling, TypeScript config, infrastructure docs, and Python comments unrelated to learning-path modules. Focused inspection did not find an active DQN module/quiz/dropout planner contract in the primary runtime path. Representative non-core or noisy hits include:

- `frontend/tsconfig.json`
- `docs/adr/0006-pipeline-v2-architecture.md`
- `docs/implementation_plan.md`
- `docs/feature_extension_design.md`
- `services/ncf/main.py`
- `services/sbert/training/train_sbert.py`
- `data/skills/skills_seed.json` with taxonomy terms such as `Quizlet`
- notebooks containing ML model architecture terms such as dropout

Conclusion: `learning_path`, `career_path`, `market_demand`, `gap_reduction`, and `estimated_skill_gap_after` are the meaningful active risk terms. `module`, `quiz`, and `dropout` are mostly noisy in the current inspected runtime.

## Files Containing DQN Session-Reranker Terminology

Meaningful `session_reranker` or `dqn_mode` terminology is not active in DQN runtime output. Representative hits:

- `CODE_REVIEW_DQN_V2_ALIGNMENT.md`
- `SCPA_Backend_ML_Plan.md`
- `reports/*/dqn/metrics.json`
- notebooks and generated reports

Runtime gap:

- `services/dqn/main.py` does not currently emit `dqn_mode = "session_reranker"`.
- `services/pipeline/stages/stage_4_dqn_rank.py` does not emit `candidate_pool_source`, `rank_before_dqn`, `rank_after_dqn`, or `reward_trace`.

## Suspected Fallback, Mock, or Synthetic Behavior

Evidence paths:

- `services/sbert/main.py` implements deterministic fallback mode and reports `fallback_mode`.
- `services/hybrid/main.py` is explicitly stale and includes fallback scoring for backward compatibility.
- `services/evaluation/thesis_evaluation_protocol.py` contains mock/random baseline behavior when data is insufficient.
- `scripts/evaluate_sample_pipeline.py` evaluates the permanent sample dataset, not production traffic.
- `reports/full_pipeline_summary.json` records sample counts and sample URLs.
- `reports/evaluation_metrics_summary.json` records `loaded_existing_artifacts`.
- `tests/test_sample_dataset_flow.py` asserts sample-data thesis targets.
- `scripts/build_evaluation_metrics_notebook.py` states SUS is not computed because no questionnaire rows are available.

## Commands Run

- `git status --short`
- `git branch --show-current`
- `git log --oneline -5`
- `Get-ChildItem -Path . -Force -Directory -Recurse -Depth 3 -Filter .git`
- `Get-Content AGENTS.md`
- `Get-Content docs/agent/TASK_QUEUE.json`
- `rg --files docs reports services tests scripts notebooks`
- `rg -n` over requested audit terms
- Focused reads of pipeline, SBERT, NCF, DQN, gateway, evaluation, and documentation files

## Tests Run

No test suite was run in Phase 0 because this phase is audit/documentation only. Validation for this deliverable is limited to file creation, Markdown inspection, and Git diff checks after Phase 1 documents are written.

## Remaining Risks

- The repo is very dirty; unrelated user or generated work must remain unstaged.
- `frontend/` is a nested Git repository and should not be mixed with root commits.
- Existing docs still contain older architecture claims.
- Runtime code still contradicts the revised DQN session-reranker contract.
- Current metrics are mostly sample/demo evidence and need stronger thesis evidence before Bab 4 claims are finalized.
