# Debug Model Report

Updated: 2026-05-31 09:12 +07

Status: initialized. Model smoke checks are pending.

## SBERT
- Target artifact: `models/sbert-indonesian-hybrid-manual-research/best`.
- Required checks: load, embedding dimension, empty input, Indonesian text, batch inference, latency, cache/fallback behavior.

## NCF / NeuMF
- Required checks: artifacts/maps, known and unknown IDs, batch scoring, output range, cold-start fallback.

## DQN
- Required checks: state shape, action space, skill/career action outputs, missing skills input, fallback.

## Calibrator
- Required checks: feature vector shape, static fallback, learned model loading, ranking output.
