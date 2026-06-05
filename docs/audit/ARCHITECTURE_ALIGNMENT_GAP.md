# Architecture Alignment Gap

Date: 2026-06-05

Scope: Phase 0 comparison of current code/docs against the revised SCPA thesis architecture contract.

## Alignment Summary

| Contract area | Current status | Severity | Summary |
|---|---|---:|---|
| SBERT semantic candidate generator | Partially aligned | P1 | SBERT scoring exists, but Top-N candidate-generator outputs and Recall@50/100 evidence are incomplete. |
| NCF historical personalization scorer | Partially aligned | P1 | Online NeuMF scoring and feedback exist, but current evidence is sample-scale and must be labeled. |
| DQN session-based dynamic reranker | Not aligned | P0 | Active code still exposes learning-path and skill-path semantics. |
| Hybrid scoring | Partially aligned | P1 | Score blending exists, but weights and fallback modes differ from revised contract. |
| Explanation layer | Partially aligned | P1 | Matched/missing skill logic exists, but explanations still leak DQN career-action/skill-path language. |
| Evaluation pipeline | Partially aligned | P1 | Metrics/reports exist, but several thesis-grade evidence outputs are missing or sample-only. |

## 1. SBERT Semantic Candidate Generator

### Required Contract

- Input: user profile text, skills, interests, resume-like text, job title, job description, required skills, preferred skills.
- Function: generate Top-N semantically relevant job candidates.
- Output: `sbert_score`, `semantic_rank`, `matched_skills`, `missing_skills`, Top-N candidate jobs.
- Evaluation: Recall@20, Recall@50, Recall@100, NDCG@10, NDCG@50, MRR@10, MAP@100, similarity distribution, error analysis.

### Current Evidence

- `services/pipeline/stages/stage_2_encode.py` builds job text from title, company, location, descriptions, skill fields, tags, and more.
- `services/pipeline/stages/stage_2_encode.py` calls SBERT `/encode`, computes cosine similarity, and emits `sbert_score`.
- `services/sbert/main.py` implements transformer inference plus explicit fallback reporting.
- `docs/MODELS.md` records a fine-tuned SBERT checkpoint and triplet/NDCG@5/Recall@5 metrics.
- `CODE_REVIEW_SBERT_V2_RETRIEVAL_ALIGNMENT.md` identifies missing retrieval-scale evidence.

### Gaps

- No explicit `semantic_rank` output in the active pipeline contract.
- `matched_skills` and `missing_skills` are handled later in aggregation/gateway, not clearly owned by SBERT candidate generation.
- The pipeline embeds and scores the provided candidate list, but the active contract does not yet enforce Top-N semantic candidate generation before NCF/DQN.
- Evidence lacks Recall@50, Recall@100, NDCG@10, NDCG@50, MRR@10, MAP@100, similarity distribution, and error-analysis CSVs.
- Fine-tuning evidence may be useful but is not sufficient alone for candidate-generator claims.

### Required Follow-Up

- Add SBERT candidate-generation evidence and Top-N outputs before claiming SBERT as a semantic candidate generator.
- Label SBERT as candidate generation, not final ranking.
- Keep deterministic fallback clearly labeled as demo/test mode.

## 2. NCF Historical Personalization Scorer

### Required Contract

- Input: `user_id`, `job_id`, historical interactions such as click, save, apply, skip, rating, dwell time.
- Function: personalize ranking using user-job interaction history.
- Output: `ncf_score`, `personalized_rank`.
- Cold-start rule: if user has no interaction history, fallback to SBERT.
- Do not overclaim NCF if interaction data is small, synthetic, or limited.

### Current Evidence

- `services/ncf/main.py` implements `OnlineNCF` and `/recommend/ncf`.
- `services/pipeline/stages/stage_3_ncf_score.py` sends user ID, interaction count, user embedding, candidate job IDs, candidates, and `sbert_score`.
- `services/pipeline/main.py` sends feedback to NCF `/feedback`.
- `reports/full_pipeline_summary.json` records NCF metrics and sample counts.
- `tests/test_ncf_neumf_contracts.py` and `tests/test_pipeline_contracts.py` cover NCF contracts.

### Gaps

- The revised output `personalized_rank` is not explicit in the pipeline output.
- Cold-start fallback is mostly enforced by hybrid weighting and SBERT dominance, not by a clearly documented NCF output contract.
- Current sample evidence has only 5 users, 9 jobs, and 21 interactions in `reports/full_pipeline_summary.json`.
- NCF contribution over SBERT-only needs a larger or clearly labeled interaction dataset.

### Required Follow-Up

- Add interaction summary, sparsity report, and contribution-over-SBERT evidence.
- Label sample/synthetic/offline interactions explicitly.
- Expose or document `personalized_rank` when NCF reranks a candidate list.

## 3. DQN Session-Based Dynamic Reranker

### Required Contract

DQN must be:

- A session-based dynamic reranker.
- A reranker only for Top-M candidates from SBERT + NCF.
- An offline or periodic learner using session logs/replay buffer.
- A real-time inference component during a user session.

DQN must not be:

- A learning-path planner.
- A career mentor.
- A module/quiz/dropout-based long-term planner.
- A raw job database selector.

Required output:

- `dqn_q_value`
- `rank_before_dqn`
- `rank_after_dqn`
- `session_interaction_count`
- `reward_trace`
- `dqn_mode = "session_reranker"`

### Current Evidence

- `services/dqn/main.py:1117` exposes `/rank`.
- `services/pipeline/stages/stage_4_dqn_rank.py` calls DQN `/rank`.
- `services/pipeline/stages/stage_4_dqn_rank.py` maps `q_value` to `dqn_q_value`.
- `services/pipeline/main.py` sends feedback to DQN `/reward`.

### Blocking Gaps

- `services/dqn/main.py:1128` exposes `/learning-path`.
- `services/gateway/main.py:3290` exposes `/api/learning-path` and calls DQN `/learning-path`.
- `services/dqn/main.py` still emits `policy_objective = "skill_path"`.
- `services/dqn/training/train_dqn.py` trains on `skill_gap_reduction + job_match_lift` with `market_demand`.
- `tests/test_dqn_learning_path.py` and `tests/test_market_aware_skill_path.py` protect the old learning-path behavior.
- `stage_4_dqn_rank.py` preserves `dqn_skill_gap`, `dqn_estimated_skill_gap_after`, and `dqn_market_demand`.
- The DQN stage does not validate candidate-pool provenance or enforce a Top-M limit.
- Current runtime does not emit `dqn_mode = "session_reranker"`.
- Current runtime does not emit `rank_before_dqn`, `rank_after_dqn`, or `reward_trace`.

### Required Follow-Up

- Phase 2 must isolate or deprecate learning-path runtime paths.
- DQN `/rank` must require SBERT/NCF candidate provenance.
- DQN rewards must be session interaction rewards: skip, view, click, save, apply, explicit relevance feedback.
- Synthetic or simulated replay data must be labeled with provenance.

## 4. Hybrid Scoring

### Required Contract

Formula:

```text
FinalScore = alpha * SBERTScore + beta * NCFScore + gamma * DQNQValue
alpha + beta + gamma = 1
```

Suggested modes:

- Cold-start: alpha `1.0`, beta `0.0`, gamma `0.0`
- History without active session: alpha `0.6`, beta `0.4`, gamma `0.0`
- Active session with small signal: alpha `0.55`, beta `0.35`, gamma `0.10`
- Active session with enough signal: alpha `0.50`, beta `0.30`, gamma `0.20`

### Current Evidence

- `services/pipeline/stages/stage_5_aggregate.py` combines `sbert_score`, `ncf_score`, and `dqn_score`.
- Current `dynamic_weights()` returns values that sum to 1.0:
  - cold: `0.75`, `0.20`, `0.05`
  - warm: `0.55`, `0.35`, `0.10`
  - active: `0.45`, `0.40`, `0.15`
- Current output includes `weights`.
- Current aggregation also adds skill alignment, penalties, and a learned calibrator.

### Gaps

- Contract names `alpha`, `beta`, `gamma` are not explicit in output.
- Cold-start still includes a DQN weight.
- Active-session thresholds do not match the revised contract.
- The final formula is not purely alpha/beta/gamma because skill alignment and calibration are applied after base scoring.
- Documentation describes several different weight sets.

### Required Follow-Up

- Decide whether calibration stays in the thesis architecture as an additional layer.
- If calibration stays, explicitly document it after the base hybrid score.
- Align weight modes with the revised contract.
- Expose `alpha`, `beta`, `gamma`, user mode, and DQN eligibility in output.

## 5. Explanation Layer

### Required Contract

- Explain why a job is recommended.
- Show matched skills.
- Show missing skills or skill gap.
- Keep skill gap individual-level.
- Do not conflate skill gap with national skill mismatch.

### Current Evidence

- `services/pipeline/stages/stage_5_aggregate.py` computes matched skills and explanation text.
- `services/gateway/main.py:1803` contains job skill-gap logic.
- `services/gateway/main.py:3660` exposes job skill-gap detail.
- `tests/test_skill_gap_detail.py` covers skill-gap behavior.

### Gaps

- Current explanation text includes `DQN career-action signal`.
- Gateway explanation provenance uses `skill_path_signal`.
- Reports include `DQN next career milestone`.
- Missing skills are present in skill-gap endpoints but not clearly part of every recommendation explanation contract.

### Required Follow-Up

- Make explanation layer independent from DQN learning path.
- Rename DQN explanation fields to session rerank terms only after runtime alignment.
- Standardize recommendation response fields: matched skills, missing skills, evidence source, score provenance.

## 6. Evaluation Pipeline

### Required Contract

The evaluation pipeline must support defensible thesis claims across dataset quality, SBERT retrieval, NCF personalization, DQN session adaptation, ablation, latency, SUS/user testing, plots, and CSVs.

### Current Evidence

- `services/evaluation/recommendation_metrics.py` implements ranking metrics.
- `reports/full_pipeline_summary.json` contains sample pipeline metrics.
- `reports/evaluation_metrics_summary.json` contains notebook/report metrics.
- `docs/EVALUATION.md` documents current metrics and limitations.
- `scripts/build_evaluation_metrics_notebook.py` states SUS is not computed because there are no questionnaire rows.
- `services/evaluation/thesis_evaluation_protocol.py` contains a protocol skeleton.

### Gaps

- No SBERT Recall@50/100 evidence artifacts were found in the required `evidence/sbert/*` layout.
- No DQN session adaptation gain, reward trace, or rank-before/after evidence artifacts were found.
- NCF interaction sparsity and contribution evidence are incomplete.
- Current fairness evidence is exploratory because sample size is very small.
- Current CTR is an offline proxy/interaction rate, not production CTR.
- `thesis_evaluation_protocol.py` uses random/mock ranking for some protocol paths when data is insufficient.
- SUS is intentionally missing because no user survey rows exist.

### Required Follow-Up

- Add evidence outputs before updating Bab 4/5 claims.
- Keep sample/demo results clearly separated from actual user-testing or production claims.
- Do not claim DQN improves recommendations until DQN-specific before/after metrics exist.

## What Was Inspected

- Git state, branch, recent commits, nested repositories.
- `AGENTS.md` and `docs/agent/TASK_QUEUE.json`.
- Pipeline stages under `services/pipeline/stages/`.
- Runtime services under `services/sbert/`, `services/ncf/`, `services/dqn/`, `services/gateway/`, `services/hybrid/`.
- Evaluation scripts and reports under `services/evaluation/`, `scripts/`, and `reports/`.
- Current architecture/model/evaluation docs.
- Existing code review documents for DQN v2 and SBERT retrieval alignment.

## What Was Changed

- This report was created.
- No runtime code was changed.

## What Was Not Changed

- No Python, TypeScript, notebook, database, service, or frontend file was edited.
- Existing dirty `docs/agent/*` files were not edited.
- No generated reports were deleted or rewritten.

## Commands Run

See `docs/audit/PROJECT_STATE_AUDIT.md` for the recovery command list and audit search commands.

## Tests Run

No runtime tests were run for this Phase 0 comparison. Validation should be performed after Phase 1 documents are written with Markdown existence checks and `git diff --check`.

## Remaining Risks

- The runtime still has P0 DQN architecture contradictions.
- Existing docs may still be read by thesis reviewers unless deprecated or corrected later.
- The evidence layer is not yet sufficient for strong Bab 4 claims.
