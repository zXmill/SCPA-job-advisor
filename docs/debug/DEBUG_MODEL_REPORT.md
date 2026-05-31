# Debug Model Report

Updated: 2026-06-01 05:15 +07

Status: static artifact inventory completed; product-quality data-signal inputs improved; live ML endpoint smoke checks pending.

## SBERT
- Target artifact: `models/sbert-indonesian-hybrid-manual-research/best`.
- Required checks: load, embedding dimension, empty input, Indonesian text, batch inference, latency, cache/fallback behavior.

## NCF / NeuMF
- Required checks: artifacts/maps, known and unknown IDs, batch scoring, output range, cold-start fallback.

## DQN
- Required checks: state shape, action space, skill/career action outputs, missing skills input, fallback.

## Calibrator
- Required checks: feature vector shape, static fallback, learned model loading, ranking output.

## Static Artifact Inventory
- SBERT best checkpoint includes `model.safetensors`, tokenizer files, `modules.json`, pooling config, and `sbert_artifact_metadata.json`.
- SBERT fine-tuning reports include baseline/final metrics, comparison CSVs, per-query CSVs, metadata, and training history.
- NCF weights include PyTorch checkpoints, manifest, online JSON state, and metrics.
- DQN weights include PyTorch checkpoint, manifest, online JSON state, and metrics.
- Calibration smoke output exists at `reports/ml/calibration_layer_smoke.json`.

## Runtime Evidence Still Needed
- Live `/health`, `/encode`, `/match/semantic`, `/predict`, `/recommend/ncf`, `/rank`, `/learning-path`, and calibration smoke checks against current code/runtime.

## Runtime Contract Pass Model Impact
- No SBERT, NCF, DQN, calibrator, model artifact, or ML training changes were made during the runtime-contract pass.
- Recommendation timeout handling changed only in the frontend to avoid false timeout UI and to align the client timeout with hybrid gateway/model latency.
- Dedicated ML runtime smoke checks remain a separate unfinished phase.

## Product Quality Data-Signal Impact
- Updated: 2026-06-01 05:15 +07.
- No SBERT, NCF, DQN, calibrator artifact, or ML training changes were made.
- Model input quality improved through data-contract changes: jobs now carry longer `description_text`, parsed `description_sections`, and required/preferred/extracted skill arrays.
- Skill-gap and recommendation explanation surfaces can now use richer job text and explicit skill arrays instead of one-line card summaries.
- Focused tests validated parser and skill extraction behavior against a rich CBI-style fixture, including Python, Linux, database design, REST APIs, Docker, Kubernetes, Airflow/Prefect, Git, MLOps, model monitoring, credit scoring, and ML/DL terminology.
- Dedicated live ML endpoint smoke checks remain an unfinished separate phase.
