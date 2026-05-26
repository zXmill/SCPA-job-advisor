# SCPA ML Model Inventory (P5-ML-001)

## Overview
This document inventories every machine-learning model, training pipeline, and evaluation artifact in the SCPA system. It is the source of truth for what exists, what is trained, and where the artifacts live.

## 1. SBERT Semantic Matcher

### Purpose
Score semantic fit between a user profile text and job descriptions. Produces the `sbert_score` used by the hybrid pipeline.

### Current Artifacts
| Artifact | Location | Status |
|----------|----------|--------|
| Base model weights | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (HuggingFace) | Available |
| Fine-tuned checkpoint | `services/sbert/weights/fine_tuned_jupyter/` | Exists (notebook-trained) |
| Similarity head | `services/sbert/training/` (trainable projection head) | Code complete |

### Architecture
- Base encoder: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim embeddings)
- Optional fine-tuning: `SimilarityHead` projection with 2-layer MLP + ReLU + cosine similarity
- Fallback: deterministic token overlap + category activation (for tests/offline)

### Hyperparameters
| Parameter | Value | Source |
|-----------|-------|--------|
| Embedding dim | 384 | Base model |
| Projection hidden dim | 384 | `SimilarityHead` |
| Learning rate | 0.002 | `train_sbert.py` |
| Weight decay | 1e-4 | `train_sbert.py` |
| Training steps | 20 | `train_sbert.py` default |
| Loss | MSE | `train_sbert.py` |
| Optimizer | AdamW | `train_sbert.py` |

### Training Entry Point
```bash
python -m services.sbert.training.train_sbert --data pairs.jsonl --output-dir ./sbert_output --steps 20
```

### Evaluation Entry Point
- `POST /match/semantic` (service endpoint)
- `tests/test_sbert_hard_negative_mining.py`
- `services/evaluation/ablation.py` (for ablation studies)

### Status
- Production-ready with fallback
- Fine-tuning pipeline exists but uses deterministic embeddings in local training (not real SBERT embeddings)
- Needs real domain data for production fine-tuning

---

## 2. NCF / NeuMF Collaborative Filter

### Purpose
Score user-job interaction fit using matrix factorization + MLP fusion. Produces the `ncf_score` used by the hybrid pipeline.

### Current Artifacts
| Artifact | Location | Status |
|----------|----------|--------|
| Online model state | `services/ncf/weights/online_ncf.json` | Persisted at runtime |
| NeuMF weights | `services/ncf/weights/online_neumf.pt` | Persisted at runtime |
| Training script | `services/ncf/training/train_ncf.py` | Code complete |

### Architecture
- Cold-start factors: initialized from SBERT embeddings
- GMF branch: element-wise product of user/item embeddings
- MLP branch: concatenated user/item embeddings through hidden layers
- Fusion: linear combination of GMF + MLP logits
- Served score: `sigmoid(0.45 * factor_logit + 0.55 * neumf_logit)`

### Hyperparameters
| Parameter | Value | Source |
|-----------|-------|--------|
| Num users | 64 (bootstrap) / dynamic | `train_ncf.py` |
| Num items | 128 (bootstrap) / dynamic | `train_ncf.py` |
| Embedding dim | 32 | `train_ncf.py` |
| Learning rate | 0.01 | `train_ncf.py` |
| Weight decay | 1e-4 | `train_ncf.py` |
| Loss | BCEWithLogitsLoss | `train_ncf.py` |
| Optimizer | AdamW | `train_ncf.py` |
| Batch size | 32 | `train_ncf.py` default |
| Steps | 25 | `train_ncf.py` default |
| Factor/neumf blend | 0.45 / 0.55 | `services/ncf/main.py` |

### Training Entry Point
```bash
python -m services.ncf.training.train_ncf --output-dir ./ncf_output --steps 25 --batch-size 32
```

### Online Learning
- `POST /feedback` to `services/ncf/main.py` triggers per-event SGD updates
- `POST /train` for batch replay training

### Evaluation Entry Point
- `POST /predict` and `POST /recommend/ncf` (service endpoints)
- `tests/test_recommendation_metrics.py`
- `services/evaluation/ablation.py`

### Status
- Production-ready with online learning
- Bootstrap training uses synthetic interactions
- Real user-item interaction data needed for production training

---

## 3. DQN Skill Policy / Reranker

### Purpose
Rerank job recommendations using a learned Q-network that optimizes for long-term user engagement (clicks, applies, skill acquisition).

### Current Artifacts
| Artifact | Location | Status |
|----------|----------|--------|
| Policy metadata | `services/dqn/weights/online_dqn.json` | Persisted at runtime |
| Policy + target weights | `services/dqn/weights/online_dqn.pt` | Persisted at runtime |
| Training bootstrap | `services/dqn/training/train.py` | Code complete |

### Architecture
- QNetwork: feed-forward MLP (state_dim -> hidden_dim -> hidden_dim -> n_actions)
- State features: projected job embedding (64-dim), SBERT score, NCF score, interaction count, user interaction count, text length, bias
- Target network: soft-updated copy (tau=0.05)
- Replay buffer: bounded store (capacity=10,000, min_size=32)
- Action space: skill vocabulary (12 skills)

### Hyperparameters
| Parameter | Value | Source |
|-----------|-------|--------|
| State dim | 70 (64 embed + 6 features) | `main.py` |
| Hidden dim | 128 | `main.py` |
| N actions | 12 (len(SKILL_VOCAB)) | `main.py` |
| Learning rate | 0.03 | `main.py` (env `DQN_LEARNING_RATE`) |
| Effective LR | 0.006 (0.03 * 0.2) | `_init_networks()` |
| Gamma | 0.92 | `main.py` (env `DQN_GAMMA`) |
| Epsilon start | 0.12 | `main.py` (env `DQN_EPSILON`) |
| Epsilon min | 0.02 | `main.py` (env `DQN_EPSILON_MIN`) |
| Epsilon decay | 0.995 | `main.py` (env `DQN_EPSILON_DECAY`) |
| Replay capacity | 10,000 | `main.py` |
| Replay min size | 32 | `main.py` (env `DQN_MIN_REPLAY_SIZE`) |
| Batch size | 16 | `main.py` (train endpoint) |
| Soft update tau | 0.05 | `soft_update()` |
| Target sync interval | 10 steps | `main.py` (env `DQN_TARGET_SYNC_INTERVAL`) |
| Weight decay | 1e-4 | `_init_networks()` |
| Optimizer | AdamW | `_init_networks()` |

### Training Entry Point
```bash
python -m services.dqn.training.train
```

### Online Learning
- `POST /reward` and `POST /feedback` trigger TD updates
- `POST /train` for batch replay training

### Evaluation Entry Point
- `POST /rank` and `POST /rerank` (service endpoints)
- `services/evaluation/ablation.py`

### Status
- Production-ready with online learning
- Bootstrap training uses synthetic positive/negative examples
- Real reward signals from user feedback drive production learning

---

## 4. Calibration Layer (Logistic Ranker)

### Purpose
Blend static hybrid scores (SBERT + NCF + DQN) with a learned logistic calibration to produce the final `calibrated_score`.

### Current Artifacts
| Artifact | Location | Status |
|----------|----------|--------|
| Calibrator code | `services/pipeline/calibration.py` | Code complete |
| Default calibrator | `get_default_calibrator()` (synthetic weights) | In-memory |
| Evaluation | `services/evaluation/calibration.py` | Smoke tests |

### Architecture
- LogisticCalibrationModel: logistic regression over 10 features
- Feature names: static_score, sbert_score, ncf_score, dqn_signal, skill_gap, skill_alignment, recency_score, salary_score, location_score, interaction_depth
- Score blend: 0.85 * logistic_prob + 0.15 * static_baseline

### Hyperparameters
| Parameter | Value | Source |
|-----------|-------|--------|
| Mode | learned_logistic | `calibration.py` |
| Model version | logistic_calibrator_synthetic_v1 | `calibration.py` |
| Baseline | static_weighted_hybrid | `calibration.py` |
| Score blend | 0.85 / 0.15 | `LogisticCalibrationModel.summary()` |
| Training source | synthetic_calibration_smoke_v1 | `calibration.py` |

### Training Entry Point
- `fit_logistic_calibrator()` in `services/pipeline/calibration.py`
- Requires labeled calibration examples (features + target score)

### Evaluation Entry Point
- `services/evaluation/calibration.py` (smoke check)
- `services/evaluation/recommendation_metrics.py` (NDCG comparison)

### Status
- Functional with synthetic weights
- Needs real labeled data for production calibration
- Smoke evaluation shows NDCG lift over static baseline

---

## 5. Hybrid Scoring Pipeline

### Purpose
Orchestrate SBERT, NCF, DQN, and calibration into a single recommendation flow.

### Current Artifacts
| Artifact | Location | Status |
|----------|----------|--------|
| Pipeline code | `services/pipeline/` | Code complete |
| Stage definitions | `services/pipeline/stages/` | 5 stages implemented |
| Calibration | `services/pipeline/calibration.py` | Integrated |

### Pipeline Stages
1. `stage_1_scrape.py` - Job ingestion
2. `stage_2_sbert_score.py` - Semantic scoring
3. `stage_3_ncf_score.py` - Collaborative filtering
4. `stage_4_dqn_rank.py` - DQN reranking
5. `stage_5_aggregate.py` - Calibration + final ranking

### Status
- Production-ready
- All 5 stages wired in gateway and pipeline service

---

## 6. Evaluation Infrastructure

### Artifacts
| Artifact | Location | Purpose |
|----------|----------|---------|
| Ranking metrics | `services/evaluation/recommendation_metrics.py` | NDCG, Precision, Recall, MAP, MRR, HitRate |
| Significance tests | `services/evaluation/significance.py` | Paired t-test, Wilcoxon signed-rank |
| Ablation framework | `services/evaluation/ablation.py` | Compare model variants |
| Calibration smoke | `services/evaluation/calibration.py` | Calibration layer validation |
| Thesis protocol | `services/evaluation/thesis_evaluation_protocol.py` | Full evaluation suite |

### Status
- Complete and tested
- Used by notebooks and CI tests

---

## Summary Table

| Model | Type | Training Data | Online Learning | Production Ready | Needs Real Data |
|-------|------|--------------|-----------------|------------------|-----------------|
| SBERT | Semantic similarity | Synthetic pairs | No | Yes (with fallback) | Yes (for fine-tuning) |
| NCF/NeuMF | Collaborative filtering | Synthetic interactions | Yes (per-event SGD) | Yes | Yes (for initial training) |
| DQN | Reinforcement learning | Synthetic rewards | Yes (TD updates) | Yes | Yes (for policy quality) |
| Calibration | Logistic regression | Synthetic examples | No | Yes (smoke weights) | Yes (for learned weights) |
