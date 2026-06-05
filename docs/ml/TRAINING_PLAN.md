# SCPA ML Training Plan (P5-ML-001)

## Overview
This document defines how each ML model in SCPA should be trained, retrained, and evaluated in production. It covers data requirements, training schedules, validation protocols, and artifact management.

## 1. SBERT Semantic Matcher

### Goal
Fine-tune `paraphrase-multilingual-MiniLM-L12-v2` on domain-specific (Indonesian + English) user-profile-to-job-description pairs so that semantic scores better reflect career relevance.

### Data Requirements
- **Positive pairs**: `(user_profile_text, job_description)` where the user applied, clicked, or saved the job
- **Hard negatives**: Same-sector jobs with skill mismatch (mined via `services/sbert/training/hard_negatives.py`)
- **Minimum dataset size**: 500 positive pairs for noticeable improvement; 2,000+ for production quality
- **Data source**: `user_interactions` table joined with `jobs` and `users`

### Training Pipeline
1. Extract positive pairs from interactions (apply, click, save = positive)
2. Mine hard negatives using sector alignment + skill gap
3. Encode pairs with base SBERT model
4. Train `SimilarityHead` projection for 20-100 steps
5. Validate: pair_accuracy > 0.75, semantic_margin > 0.15

### Entry Point
```bash
python -m services.sbert.training.train_sbert \
  --data data/sbert_training_pairs.jsonl \
  --output-dir services/sbert/weights/fine_tuned_v2 \
  --steps 50
```

### Retraining Schedule
- **Initial**: After collecting 500+ positive pairs
- **Periodic**: Monthly or when pair_accuracy on holdout drops below 0.70
- **Trigger**: When A/B test shows treatment variant (new weights) beats control

### Validation
- Holdout 20% of pairs for validation
- Target: pair_accuracy >= 0.75, semantic_margin >= 0.15
- Cross-check with `tests/test_sbert_hard_negative_mining.py`

---

## 2. NCF / NeuMF Collaborative Filter

### Goal
Train the NeuMF model on real user-item interactions so that `ncf_score` reflects actual preference patterns rather than synthetic patterns.

### Data Requirements
- **Positive interactions**: view, click, save, apply events
- **Negative sampling**: Unseen jobs or explicit skips (4:1 negative-to-positive ratio)
- **Minimum dataset size**: 100 users x 50 items for cold-start viability; 1,000+ users for production
- **Data source**: `user_interactions` + `jobs` tables

### Training Pipeline
1. Build user-item interaction matrix from `user_interactions`
2. Sample negatives (random unseen jobs + explicit skips)
3. Initialize cold-start factors from SBERT embeddings
4. Train NeuMF with BCEWithLogitsLoss for 25-100 steps
5. Validate: top5_accuracy > 0.60, NDCG@5 > 0.50

### Entry Point
```bash
python -m services.ncf.training.train_ncf \
  --output-dir services/ncf/weights/batch_trained \
  --steps 50 \
  --batch-size 64
```

### Retraining Schedule
- **Initial**: After collecting 1,000+ interactions
- **Periodic**: Weekly batch retrain from full interaction history
- **Online**: Continuous per-event updates via `POST /feedback`
- **Trigger**: When NDCG@5 on holdout interactions drops below 0.45

### Validation
- Time-based split: train on weeks 1-3, validate on week 4
- Target: top5_accuracy >= 0.60, NDCG@5 >= 0.50
- Cross-check with `services/evaluation/ablation.py` (ncf_only variant)

---

## 3. DQN Skill Policy / Reranker

### Goal
Learn a Q-network policy that maximizes long-term user engagement by recommending the right skills to acquire.

### Data Requirements
- **Transitions**: `(state, action, reward, next_state, done)` tuples
- **Rewards**: Derived from feedback events (click=+1.0, apply=+1.0, skip=-0.5, etc.)
- **Minimum dataset size**: 500 transitions for viable learning; 2,000+ for stable policy
- **Data source**: `feedback_events` + DQN replay buffer

### Training Pipeline
1. Collect transitions from `feedback_events` (convert events to rewards)
2. Bootstrap replay buffer with historical transitions
3. Train QNetwork with TD updates for 100-500 steps
4. Soft-update target network (tau=0.05)
5. Validate: policy selects positive job over negative job > 80% of the time

### Entry Point
```bash
python -m services.dqn.training.train
# Or batch train via service endpoint:
curl -X POST http://dqn:8004/train -d '{"batch_size": 32}'
```

### Retraining Schedule
- **Initial**: After collecting 500+ transitions
- **Periodic**: Daily batch train from replay buffer
- **Online**: Every feedback event triggers a TD update
- **Trigger**: When epsilon-greedy policy performance on holdout drops below 0.75

### Validation
- Holdout 20% of transitions for policy evaluation
- Target: policy accuracy >= 0.80 on positive-vs-negative ranking
- Cross-check with `services/evaluation/ablation.py` (dqn_only variant)

---

## 4. Calibration Layer

### Goal
Learn logistic weights that optimally blend static hybrid scores into a calibrated final score.

### Data Requirements
- **Labeled examples**: `(features, target_score)` where target_score is derived from user feedback
- **Features**: static_score, sbert_score, ncf_score, dqn_signal, skill_gap, skill_alignment, recency_score, salary_score, location_score, interaction_depth
- **Minimum dataset size**: 200 labeled examples; 1,000+ for stable weights
- **Data source**: `feedback_events` + `served_slate_items` + hybrid scores

### Training Pipeline
1. Extract calibration features from served recommendations
2. Derive target scores from feedback (click=1.0, skip=0.0, apply=1.0)
3. Fit logistic regression with L2 regularization
4. Validate: calibrated NDCG@5 > static NDCG@5 by at least 0.03

### Entry Point
```python
from services.pipeline.calibration import fit_logistic_calibrator
calibrator = fit_logistic_calibrator(examples)
```

### Retraining Schedule
- **Initial**: After collecting 200+ labeled examples
- **Periodic**: Weekly retrain from last 30 days of feedback
- **Trigger**: When calibrated NDCG lift drops below 0.02

### Validation
- Time-based split: train on days 1-21, validate on days 22-30
- Target: calibrated NDCG@5 >= static NDCG@5 + 0.03
- Cross-check with `services/evaluation/calibration.py`

---

## 5. Cross-Model Evaluation Protocol

### Goal
Ensure the full hybrid pipeline (SBERT + NCF + DQN + Calibration) meets production quality targets.

### Evaluation Pipeline
1. **Ablation study**: Run all 7 variants (sbert_only, ncf_only, dqn_only, sbert_ncf, sbert_dqn, ncf_dqn, full_scpa)
2. **Metrics**: NDCG@5, NDCG@10, Precision@5, Recall@5, MAP@5, MRR@5, HitRate@5
3. **Significance**: Paired t-test or Wilcoxon signed-rank for full_scpa vs best single model
4. **Fairness**: Check group TPR parity across user segments (program studi, experience level)
5. **Latency**: P95 latency < 500ms for full pipeline

### Entry Point
```python
from services.evaluation.ablation import evaluate_ablation
from services.evaluation.significance import compare_paired
report = evaluate_ablation(rankings_by_variant, relevant_by_user, k=5)
```

### Production Targets
| Metric | Target | Critical |
|--------|--------|----------|
| NDCG@5 | >= 0.55 | Yes |
| NDCG@10 | >= 0.60 | Yes |
| Precision@5 | >= 0.45 | Yes |
| HitRate@5 | >= 0.70 | Yes |
| MAP@5 | >= 0.50 | No |
| MRR@5 | >= 0.55 | No |
| Fairness gap | <= 10 pp | Yes |
| P95 latency | <= 500 ms | Yes |

---

## 6. Artifact Management

### Versioning
- All model weights stored with versioned filenames (e.g., `online_ncf_2026-05-26.pt`)
- Metadata JSON accompanies each checkpoint (hyperparameters, training date, metrics)

### Storage
- **Local**: `services/<model>/weights/`
- **Production**: Mount weights directory as Docker volume or S3-compatible storage
- **Backup**: Copy weights to `data/model_backups/` before retraining

### Rollback
- Keep last 3 checkpoints per model
- Gateway can switch between checkpoints via environment variable or experiment variant

---

## 7. Monitoring

### Model Health
- Each service exposes `/health` and `/model/status`
- Gateway aggregates health in `/health` response
- Alert when any model health != "healthy" for > 5 minutes

### Performance Drift
- Log NDCG@5 on a weekly holdout set
- Alert when NDCG@5 drops by > 10% from baseline
- Trigger retraining when drift detected

### A/B Testing
- Use `P4-ADV-004` experiment infrastructure to compare model variants
- Run experiments for at least 7 days or 100 users per variant
- Use `services/evaluation/significance.py` for statistical testing
