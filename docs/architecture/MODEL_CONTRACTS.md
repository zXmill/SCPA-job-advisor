# Model Contracts

Date: 2026-06-05

This document defines the model-level contracts for the revised SCPA architecture. These contracts are normative for future runtime and evidence work.

## 1. SBERT Contract

### Role

SBERT is a semantic candidate generator.

### Inputs

User-side inputs:

- `user_id`
- `profile_text`
- `skills`
- `interests`
- Resume-like text
- Study program or career intent when available

Job-side inputs:

- `job_id`
- `title`
- `description`
- `required_skills`
- `preferred_skills`
- `company`
- `location`
- Optional tags or extracted skill fields

### Required Processing

- Normalize user and job text.
- Encode user text and job text.
- Compute semantic similarity.
- Sort candidates by semantic relevance.
- Produce a Top-N candidate pool for downstream NCF and DQN.

### Required Outputs

- `job_id`
- `sbert_score`
- `semantic_rank`
- `matched_skills`
- `missing_skills`
- `embedding_model_name`
- `embedding_model_version`
- `fallback_mode`
- `candidate_pool_size`

### Required Evaluation

- Recall@20
- Recall@50
- Recall@100
- NDCG@10
- NDCG@50
- MRR@10
- MAP@100
- Similarity distribution
- Error analysis
- Lexical baseline comparison when available
- Base SBERT versus fine-tuned SBERT comparison

### Non-Claims

- SBERT is not the full recommender.
- SBERT Top-5 quality alone does not prove candidate-generator quality.
- Deterministic fallback output is not evidence of transformer quality.

## 2. NCF Contract

### Role

NCF is a historical personalization scorer.

### Inputs

- `user_id`
- `job_id`
- Candidate job IDs from SBERT candidate generation
- Historical events:
  - impression
  - view
  - click
  - save
  - apply
  - skip
  - rating
  - dwell time
- Optional profile and job embeddings

### Required Processing

- Train or update from historical user-job interactions.
- Score only candidates in the current candidate pool.
- Provide personalization score and rank.
- Degrade gracefully for cold-start users.

### Required Outputs

- `job_id`
- `ncf_score`
- `personalized_rank`
- `interaction_count`
- `interaction_data_provenance`
- `cold_start = true/false`
- `model_version`

### Required Evaluation

- Number of users.
- Number of jobs.
- Number of interactions.
- Event distribution.
- Matrix sparsity.
- HitRate@K.
- NDCG@K.
- Contribution over SBERT-only baseline.
- Cold-start analysis.

### Cold-Start Rule

If a user has no interaction history:

- NCF must not dominate final ranking.
- Hybrid scoring should use beta `0.0` or label any NCF score as fallback/neutral.
- The thesis must state that personalization depends on interaction availability.

### Non-Claims

- Do not claim strong personalization from small or synthetic interaction data.
- Do not call offline proxy CTR production CTR.

## 3. DQN Contract

### Role

DQN is a session-based dynamic reranker.

### Inputs

Candidate-pool inputs:

- Top-M candidate job IDs from SBERT + NCF.
- `sbert_score` per candidate.
- `ncf_score` per candidate, or explicit cold-start fallback flag.
- Candidate features and embeddings.
- `candidate_pool_source = "sbert_ncf"`.

Session-state inputs:

- Recent viewed jobs.
- Recent clicked jobs.
- Recent skipped jobs.
- Recent saved jobs.
- Recent applied jobs.
- Dwell-time summary.
- Session intent embedding.
- Interaction count.

### Required Guards

- DQN must reject or mark invalid candidates without SBERT/NCF provenance.
- DQN must not query or select from the raw job database.
- Candidate count must be bounded by configured Top-M.
- DQN output must include enough provenance to prove it was used as a reranker.

### State

The DQN state is session-local and candidate-pool aware:

```text
state = recent_session_events
      + dwell_time_summary
      + session_intent_embedding
      + candidate_pool_features
      + interaction_count
```

### Action

The DQN action is:

```text
promote_or_rerank(candidate_job_from_top_m)
```

### Reward

| Event | Reward |
|---|---:|
| quick_skip | -0.2 |
| short_view_without_action | -0.1 |
| click_job_detail | 1.0 |
| save_or_bookmark | 2.0 |
| apply | 3.0 |
| explicit_relevant_feedback | 2.0 |
| explicit_irrelevant_feedback | -1.0 |

### Required Outputs

- `job_id`
- `dqn_mode = "session_reranker"`
- `candidate_pool_source = "sbert_ncf"`
- `dqn_q_value`
- `rank_before_dqn`
- `rank_after_dqn`
- `session_interaction_count`
- `reward_trace` or `reward_summary`
- `model_version`
- `training_mode`
- `dataset_provenance`

### Required Evaluation

- NDCG@K before DQN.
- NDCG@K after DQN.
- Session Adaptation Gain.
- Average reward per session.
- Interaction lift.
- Rank movement after feedback.
- DQN ablation against SBERT + NCF.

### Non-Claims

- DQN is not a learning-path planner.
- DQN is not a career mentor.
- DQN is not a long-term career trajectory model.
- DQN does not learn perfectly in real time.
- DQN does not improve recommendations unless DQN-specific evidence proves it.

## 4. Hybrid Scoring Contract

### Role

Hybrid scoring fuses SBERT, NCF, and DQN signals into a final score.

### Inputs

- `sbert_score`
- `ncf_score`
- `dqn_q_value`
- user interaction count
- session interaction count
- fallback flags
- model provenance

### Required Formula

```text
final_score = alpha * sbert_score + beta * ncf_score + gamma * dqn_q_value
```

Required constraint:

```text
alpha + beta + gamma = 1
```

### Required Modes

| Mode | alpha | beta | gamma |
|---|---:|---:|---:|
| cold_start | 1.00 | 0.00 | 0.00 |
| historical_only | 0.60 | 0.40 | 0.00 |
| active_small_signal | 0.55 | 0.35 | 0.10 |
| active_enough_signal | 0.50 | 0.30 | 0.20 |

### Required Outputs

- `final_score`
- `alpha`
- `beta`
- `gamma`
- `scoring_mode`
- `score_components`
- `model_provenance`
- `fallback_flags`

### Calibration Contract

If calibration is used:

- Emit `base_hybrid_score`.
- Emit `calibrated_score`.
- Explain calibration features.
- Do not present calibrated score as the raw alpha/beta/gamma formula.

## 5. Explanation Layer Contract

### Role

The explanation layer turns ranking evidence into user-facing reasons.

### Inputs

- User skills.
- Job required/preferred skills.
- Matched skills from semantic and skill extraction logic.
- Missing skills.
- Score components.
- Model provenance.
- Fallback flags.

### Required Outputs

- `matched_skills`
- `missing_skills`
- `skill_gap_summary`
- `why_recommended`
- `score_breakdown`
- `model_provenance`

### Rules

- Skill gap is individual-level only.
- Skill gap must compare one user's skills with one job's requirements.
- Skill gap must not be described as national skill mismatch.
- Explanations must not imply DQN planned a learning path.
- Explanations must clearly label fallback or simulated evidence.

### Safe Wording

- "This job matches your Python and SQL skills."
- "The current gap is Docker and Redis based on this job's listed requirements."
- "The recommendation score combines semantic fit, historical preference signal, and session reranking when available."

### Forbidden Wording

- "This solves Indonesia's skill mismatch."
- "DQN planned your career path."
- "The system guarantees a correct career trajectory."
- "Production CTR improved" when only offline interaction rate exists.

## 6. Evidence Provenance Contract

Every evaluation output should state:

- `dataset_name`
- `dataset_provenance`
- `real_user_data = true/false`
- `evaluation_mode`
- `model_versions`
- `fallback_flags`
- `sample_size`
- `generated_at`
- regeneration command

Accepted provenance values:

- `real_user_session_data`
- `live_scraper_data`
- `curated_sample`
- `synthetic`
- `offline_simulation`
- `ci_fallback`

## What Was Inspected

- Revised architecture contract from the user request.
- Current model and pipeline implementation.
- Current reports and docs listed in Phase 0 audit files.

## What Was Changed

- This model contract document was created.
- Runtime model code was not changed.

## Tests Run

No runtime tests were run for this documentation-only contract.

## Remaining Risks

- Runtime output does not yet satisfy DQN session-reranker fields.
- Hybrid weights do not yet match this contract.
- Evidence provenance is inconsistent across current reports.
