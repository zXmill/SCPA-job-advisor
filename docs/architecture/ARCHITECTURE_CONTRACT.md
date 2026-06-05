# SCPA Architecture Contract

Date: 2026-06-05

This is the Phase 1 target architecture contract for the revised SCPA thesis framing. Runtime code must be aligned to this contract in later phases before stronger thesis claims are made.

## Final SCPA Architecture

SCPA is a hybrid multi-stage career recommendation and skill-gap explanation system.

The system supports individual career decision-making by:

1. Matching a user profile to job requirements.
2. Ranking relevant job candidates.
3. Personalizing ranking when historical interaction data exists.
4. Reranking during an active session when session feedback exists.
5. Explaining matched and missing skills at the individual user-job level.

The system does not claim to solve national skill mismatch or transform the labor market.

## Active Model Roles

| Component | Role | Must not be framed as |
|---|---|---|
| SBERT | Semantic candidate generator | Final recommender by itself |
| NCF | Historical personalization scorer | Strong personalization without sufficient interaction data |
| DQN | Session-based dynamic reranker | Learning-path planner, career mentor, raw database selector |
| Hybrid scoring | Score fusion layer | Proof that complexity alone improves results |
| Explanation layer | Matched/missing skill explanation | National skill-mismatch measurement |

## Runtime Flow

```text
User profile and skills
-> SBERT semantic candidate generation
-> Top-N candidate jobs
-> NCF historical personalization scoring
-> Top-M candidate pool
-> DQN session-based reranking, only when session signal exists
-> Hybrid scoring
-> Explanation layer: matched skills, missing skills, score provenance
-> Ranked job recommendations
```

## SBERT Role

SBERT is the semantic candidate generator.

Allowed inputs:

- User profile text.
- Skills and interests.
- Resume-like text.
- Job title.
- Job description.
- Required skills.
- Preferred skills.

Required function:

- Generate Top-N semantically relevant job candidates.
- Provide semantic scores and semantic ranking.
- Feed a bounded candidate pool to NCF and DQN.

Required outputs:

- `sbert_score`
- `semantic_rank`
- `matched_skills`
- `missing_skills`
- Top-N candidate job IDs and metadata

Required evaluation:

- Recall@20
- Recall@50
- Recall@100
- NDCG@10
- NDCG@50
- MRR@10
- MAP@100
- Similarity distribution
- Error analysis

Fallback rule:

- SBERT deterministic fallback may be used only for CI/demo/offline resilience.
- Any fallback output must expose `fallback_mode = true` and must not be cited as transformer-model evidence.

## NCF Role

NCF is the historical personalization scorer.

Allowed inputs:

- `user_id`
- `job_id`
- Historical interactions:
  - click
  - save
  - apply
  - skip
  - rating
  - dwell time
- Candidate job features produced after SBERT candidate generation.

Required function:

- Personalize ranking using user-job interaction history.
- Produce a personalization score for each candidate.

Required outputs:

- `ncf_score`
- `personalized_rank`
- Interaction-data provenance

Cold-start rule:

- If the user has no interaction history, NCF must not dominate ranking.
- Cold-start users fall back to SBERT-only or SBERT-dominant scoring.
- If interaction data is limited, synthetic, seeded, or simulated, the output must label that provenance.

Required evaluation:

- Number of users.
- Number of jobs.
- Number of interactions.
- Interaction matrix sparsity.
- HitRate@K.
- NDCG@K.
- Contribution over SBERT-only baseline.
- Cold-start analysis.

## DQN Role

DQN is the session-based dynamic reranker.

Allowed function:

- Rerank Top-M candidates already produced by SBERT + NCF.
- Perform real-time inference during a user session.
- Learn offline or periodically from session logs/replay buffer.

Forbidden function:

- DQN must not be a learning-path planner.
- DQN must not be a career mentor.
- DQN must not be a module/quiz/dropout planner.
- DQN must not select jobs directly from the raw database.
- DQN must not be claimed to learn perfectly in real time.

Required state:

- Recently viewed jobs.
- Recently clicked jobs.
- Recently skipped jobs.
- Recently saved or applied jobs.
- Dwell-time summary.
- Session intent embedding.
- Current candidate-pool features.
- Interaction count.

Required action:

- Promote or rerank a candidate job from the Top-M candidate pool.

Required rewards:

| Session event | Reward |
|---|---:|
| Quick skip | -0.2 |
| Short view without action | -0.1 |
| Click job detail | 1.0 |
| Save/bookmark | 2.0 |
| Apply | 3.0 |
| Explicit relevant feedback | 2.0 |
| Explicit irrelevant feedback | -1.0 |

Required outputs:

- `dqn_mode = "session_reranker"`
- `candidate_pool_source = "sbert_ncf"`
- `dqn_q_value`
- `rank_before_dqn`
- `rank_after_dqn`
- `session_interaction_count`
- `reward_trace` or `reward_summary`
- `dataset_provenance` when training or evaluation is simulated

Required guards:

- Candidate count must be bounded by Top-M.
- Candidates must include `sbert_score`.
- Candidates must include `ncf_score`, unless the system explicitly declares cold-start fallback.
- Candidates must carry provenance showing they came from the SBERT/NCF candidate pool.

Required evaluation:

- Average reward per session.
- Session adaptation gain.
- Interaction lift.
- NDCG@K before DQN.
- NDCG@K after DQN.
- Rank movement after session feedback.

## Hybrid Scoring

Base formula:

```text
FinalScore = alpha * SBERTScore + beta * NCFScore + gamma * DQNQValue
```

Constraint:

```text
alpha + beta + gamma = 1
```

Required modes:

| Mode | Condition | alpha | beta | gamma |
|---|---|---:|---:|---:|
| Cold-start | No interaction history | 1.00 | 0.00 | 0.00 |
| Historical only | History exists, no active session signal | 0.60 | 0.40 | 0.00 |
| Active small signal | Active session with limited signal | 0.55 | 0.35 | 0.10 |
| Active enough signal | Active session with enough signal | 0.50 | 0.30 | 0.20 |

Required outputs:

- `final_score`
- `alpha`
- `beta`
- `gamma`
- `scoring_mode`
- `sbert_score`
- `ncf_score`
- `dqn_q_value`
- `model_provenance`
- `fallback_flags`

Calibration rule:

- If a learned calibrator or additional skill-alignment adjustment is used, it must be documented as a post-fusion calibration layer.
- The thesis must not hide calibration inside the base formula.

## Explanation Layer

The explanation layer explains individual recommendation reasons.

Required outputs:

- Matched skills.
- Missing skills.
- Individual-level skill gap.
- Score provenance.
- Model contribution summary.
- Fallback/provenance flags.

Allowed claim:

- The system identifies the gap between one user's skills and one job's requirements.

Forbidden claim:

- The system measures or solves national skill mismatch.

## Fallback Rules

SBERT fallback:

- Allowed for CI/demo/local resilience.
- Must be labeled with `fallback_mode = true`.
- Must not be used as evidence for transformer model quality.

NCF fallback:

- If insufficient interaction history exists, set beta to `0.0` or clearly label cold-start behavior.
- Do not overclaim personalization.

DQN fallback:

- If no active session signal exists, set gamma to `0.0`.
- Do not fabricate DQN session adaptation.

Data fallback:

- Sample data may keep demos runnable.
- Sample data must be labeled as sample/demo evidence.
- Production or national-scale claims require separate evidence.

## What SCPA Does Not Claim

SCPA does not claim:

- To solve national skill mismatch in Indonesia.
- To transform the labor market.
- To prove production CTR from offline interactions.
- To prove fairness validity from a tiny sample.
- To prove Kubernetes production readiness unless Kubernetes was actually deployed and tested.
- To prove DQN session adaptation without before/after DQN session metrics.
- To prove NCF strength without sufficient interaction data.
- To prove simulated metrics are actual user results.

## Future Work

The following must be future work unless implemented and tested:

- Learning path generation.
- Long-term career mentor behavior.
- Module/quiz/dropout planning.
- Kubernetes deployment and production readiness.
- National labor-market skill-mismatch measurement.
- Production CTR.
- Full user-study SUS claims.
- Large-scale fairness audit.

## Phase 2 Gate

Runtime code alignment may begin only after this contract is accepted. Phase 2 must focus on DQN v2 alignment and must not rewrite unrelated architecture.

## What Was Inspected

This contract was derived from:

- User-provided revised architecture contract.
- `docs/audit/PROJECT_STATE_AUDIT.md`
- `docs/audit/ARCHITECTURE_ALIGNMENT_GAP.md`
- Current pipeline, gateway, SBERT, NCF, DQN, hybrid, and evaluation files.

## What Was Changed

- This architecture contract was created.
- Runtime code was not changed.

## Tests Run

No runtime tests were run for this documentation-only contract.

## Remaining Risks

- Runtime code is not yet aligned with this contract.
- Existing docs still contain old learning-path and career-milestone framing.
- Evidence artifacts still need to be generated before final thesis claims.
