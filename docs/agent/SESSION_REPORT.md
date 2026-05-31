
## Task Completion: P5-ML-001 (ML Inventory and Training Plan)

### What was done
- Wrote `docs/ml/ML_INVENTORY.md` cataloging all 5 ML components:
  - SBERT semantic matcher (base model, fine-tuned checkpoint, similarity head, hyperparameters)
  - NCF/NeuMF collaborative filter (online model, training script, hyperparameters)
  - DQN skill policy/reranker (QNetwork, replay buffer, target network, hyperparameters)
  - Calibration layer (logistic ranker, feature names, score blend)
  - Hybrid scoring pipeline (5 stages)
  - Evaluation infrastructure (metrics, significance tests, ablation framework)
- Wrote `docs/ml/TRAINING_PLAN.md` with:
  - Data requirements for each model
  - Training pipelines and entry points
  - Retraining schedules (initial, periodic, online, trigger-based)
  - Validation protocols and production targets
  - Artifact management and rollback procedures
  - Monitoring and drift detection
- Added 8 smoke tests in `tests/test_ml_inventory_and_training_plan.py`

### Validation
- Backend tests: `382 passed, 2 warnings`

## Task Completion: P5-ML-002 through P5-ML-005 (Model Evaluation)

### What was done
- Created `scripts/eval/evaluate_sbert.py` (P5-ML-002):
  - Loads test pairs, scores with deterministic fallback embeddings
  - Computes Precision@K, Recall@K, NDCG@K, HitRate@K
  - Generates synthetic test data if none exists
- Created `scripts/eval/evaluate_ncf.py` (P5-ML-003):
  - Builds train/test split from synthetic interactions
  - Adds negative sampling with bounded generation (fixed infinite loop bug)
  - Trains minimal `_NeuralCF` model offline
  - Computes ranking metrics on held-out test set
- Created `scripts/eval/evaluate_dqn.py` (P5-ML-004):
  - Runs offline simulation with positive vs negative job scenarios
  - Compares learned policy vs random baseline
  - Reports policy accuracy, Precision@K, NDCG@K, HitRate@K
- Created `scripts/eval/evaluate_calibrator.py` (P5-ML-005):
  - Evaluates calibration layer on synthetic examples
  - Computes static vs calibrated NDCG lift
  - Reports per-feature importance
- Added 4 tests in `tests/test_model_evaluation_scripts.py`

### Validation
- Backend tests: `386 passed, 2 warnings`
- All evaluation scripts run successfully and produce report JSON files

## Session Summary

All pending tasks from the task queue have been completed:
- `P2-005` — Calibration layer (was stale, marked done)
- `P4-ADV-004` — A/B testing and monitoring (design + smoke implementation)
- `P5-ML-001` — ML inventory and training plan docs
- `P5-ML-002` — Evaluate SBERT recommender
- `P5-ML-003` — Evaluate NeuMF recommender
- `P5-ML-004` — Evaluate DQN skill policy
- `P5-ML-005` — Evaluate recommendation calibrator

Final test count: **386 passed, 2 warnings**
Branch: `agent-run`

## Task Completion: P5-ML-007 (Fine-tuned SBERT Runtime Integration)

### What was done
- Integrated the checkpoint from `notebooks/03_sbert_fine_tuning_hybrid_research_manual_v3.ipynb` by making the SBERT service load `models/sbert-indonesian-hybrid-manual-research/best`.
- Added a `transformers` serving loader with SentenceTransformer-compatible mean pooling and L2 normalization to avoid importing the notebook/training stack in service runtime.
- Docker Compose now mounts the fine-tuned `best` checkpoint into `/app/weights/sbert` and sets `SBERT_MODEL_LOADER=transformers`.
- SBERT `/health`, `/metrics`, `/match/semantic`, and `/encode` now expose the active `model_version`.
- Pipeline stage 2 now preserves the SBERT `model_version` in its stage summary.
- Updated model docs and ML inventory to point to the active fine-tuned artifact, metrics, and runtime path.
- Added `tests/test_sbert_finetuned_runtime.py` for artifact metadata and real runtime loading without fallback.
- Ignored `SCPAv2` as requested.

### Validation
- Artifact reload smoke: passed, `sbert-indonesian-hybrid-manual-research-best`, dim 384, fallback false.
- Focused SBERT runtime tests: `2 passed`.
- SBERT cache and pipeline job embedding cache tests: `17 passed`.
- Docker Compose config: passed with dummy required env vars.
- Full backend suite: `389 passed, 3 warnings`.
- Commit: `0313e8a`.

## Task Start: DEBUG-ULT-001 (Ultimate Evidence-Based Debugging Session)

### What is being done
- Initialized required debug-session documentation under `docs/debug/`.
- Marked `DEBUG-ULT-001` active in `docs/agent/TASK_QUEUE.json`.
- Recorded that `morph-mcp` was requested but no callable morph tool is exposed in the current tool surface.
- No product code has been changed.

### Next validation
- `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- `git status --short --branch`
- staged diff inspection before committing initialization docs.

### Baseline results
- Initialization commit: `0b55041`.
- Static inventory completed for FastAPI routes, frontend routes/components, migrations, Docker services, CI workflow, and ML artifacts.
- Backend: `.\.venv\Scripts\python.exe scripts\verify_project.py --only import compile` passed.
- Backend: `.\.venv\Scripts\python.exe -m pytest -q` passed with 389 tests and 3 warnings.
- Frontend: `npm run lint` passed with 16 warnings.
- Frontend: `npm run build` passed.
- Docker: `docker compose config --quiet` passed.
- Docker: `docker compose up -d --build` failed while rebuilding gateway because pip could not open `requirements-db.txt`; the gateway build context transfer reached about 5.06GB.
- Runtime caveat: existing Docker containers report healthy on gateway port 9000, but they were created before the failed rebuild and are not current-image proof.

### Confirmed issues
- `H1-DOCKER-GATEWAY-REQ`: gateway Docker build dependency layer is broken.
- `H2-DOCKER-CONTEXT`: root `.dockerignore` is missing, producing an oversized build context.
- `H4-DOCKER-PORT-CONTRACT`: current frontend env uses port 9000, while port 8000 is not listening.
