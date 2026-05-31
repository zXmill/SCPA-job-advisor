# Debug Model Report

Updated: 2026-05-31 21:41 +07

Status: static artifact inventory completed; runtime smoke checks pending.

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
