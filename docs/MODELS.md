# Model Documentation

## Overview

SCPA uses three model signals and one aggregation layer:

- SBERT for semantic user-job matching.
- NCF for user-job interaction scoring.
- DQN for career milestone/action recommendation.
- Hybrid aggregation for final job recommendation ranking.

The production/demo path is lightweight and reproducible with the permanent sample dataset.

## SBERT

### Purpose

SBERT scores how semantically close a user profile is to each job listing. It is especially useful for cold-start users with little interaction history.

### Input

- User profile text from `profile_text`, skills, study program, and target role.
- Job text formed from title, company, location, description, and skills/tags.

### Output

- `sbert_score` for each user-job pair.
- SBERT-only ranking metrics in `reports/full_pipeline_metrics.csv`.
- Active fine-tuned artifact: `models/sbert-indonesian-hybrid-manual-research/best`.
- Runtime model version: `sbert-indonesian-hybrid-manual-research-best`.

### Training and Prediction

The active SBERT checkpoint was produced by:

```text
notebooks/03_sbert_fine_tuning_hybrid_research_manual_v3.ipynb
```

The notebook fine-tunes `paraphrase-multilingual-MiniLM-L12-v2` with a manual
PyTorch loop and `MultipleNegativesRankingLoss`, then saves:

- `models/sbert-indonesian-hybrid-manual-research/best`
- `models/sbert-indonesian-hybrid-manual-research/final`
- metrics and comparison files under `models/sbert-indonesian-hybrid-manual-research/artifacts`

Current artifact evidence:

- Validation triplet accuracy: `0.997455`
- Test triplet accuracy: `0.997396`
- Test NDCG@5: `0.511467`
- Test Recall@5: `0.626459`
- Baseline-to-fine-tuned NDCG@5 delta: `+0.367729`

Docker Compose mounts the `best` checkpoint into the SBERT container at
`/app/weights/sbert` and sets `MODEL_DIR=/app/weights/sbert`.

The service uses `transformers` directly for inference with mean pooling and L2
normalization, so it serves the fine-tuned weights without importing the
notebook training stack.

Legacy lightweight retraining is still available for smoke artifacts:

```powershell
python scripts\retrain_pipeline.py --output-dir reports\retraining_artifacts --steps 1
```

Full pipeline training/scoring is triggered through:

```powershell
python scripts\run_full_pipeline.py --steps 1 --limit 5
```

CI/demo mode can force deterministic fallback embeddings:

```powershell
$env:SBERT_FORCE_FALLBACK='1'
$env:SBERT_ENABLE_TRANSFORMER='0'
```

## NCF

### Purpose

NCF scores jobs from user interaction behavior. It learns from clicks, saves, applications, views, skips, and labels in `data/sample/interactions.jsonl`.

### Input

- `user_id`
- job candidates
- interaction events and labels
- optional profile context

### Output

- `ncf_score` for each candidate job.
- NCF-only ranking metrics.
- Artifact: `reports/full_pipeline_artifacts/ncf/online_ncf.json`.

### Training and Prediction

The lightweight retraining flow writes/updates the online artifact:

```powershell
python scripts\retrain_pipeline.py --output-dir reports\retraining_artifacts --steps 1
```

The full pipeline loads or regenerates artifacts and writes final reports:

```powershell
python scripts\run_full_pipeline.py --steps 1 --limit 5
```

## DQN

### Purpose

DQN recommends career milestones/actions for a user's target role. It also produces a rerank signal used by the hybrid job recommendation pipeline.

### Input

- `user_id`
- current skills
- target role
- career milestone/action labels from `data/sample/milestones.jsonl`
- optional job candidates for rerank scoring

### Output

- `career_path.career_milestones`
- `dqn_score` for job reranking
- DQN action metrics in `reports/evaluation_metrics_summary.json`
- Artifacts:
  - `reports/full_pipeline_artifacts/dqn/dqn_model.pt`
  - `reports/full_pipeline_artifacts/dqn/online_dqn.json`

### Training and Prediction

The DQN retraining output from the latest full pipeline run reports:

- Status: `trained`
- Mean TD error: `0.301914`
- Validation reward: `0.310938`
- Random reward: `0.188235`
- Reward lift vs random: `1.651856`

DQN must be explained as a career milestone/action recommender, not as a random job posting recommender.

## Hybrid Recommendation

### Purpose

Hybrid aggregation combines SBERT, NCF, and DQN signals into a final ranked job list.

### Input

For each candidate job:

- `sbert_score`
- `ncf_score`
- `dqn_score`
- job metadata
- user interaction history context

### Output

Each final recommendation includes:

- `job_id`
- `title`
- `company`
- `company_logo`
- `location`
- `source_url`
- `final_score`
- `sbert_score`
- `ncf_score`
- `dqn_score`
- `weights`
- `explanation`

The final response also includes `career_path` with DQN milestones/actions.

### Aggregation Behavior

The latest generated recommendation output shows warm-user weights:

- SBERT: `0.4`
- NCF: `0.3`
- DQN: `0.3`

Cold-start behavior uses SBERT more heavily, and failure-mode tests verify safe fallbacks when models or artifacts are unavailable.

## Artifact Save/Load Process

| Artifact | Latest path |
|---|---|
| SBERT fine-tuned checkpoint | `models/sbert-indonesian-hybrid-manual-research/best` |
| SBERT notebook metrics | `models/sbert-indonesian-hybrid-manual-research/artifacts/` |
| SBERT smoke artifact | `reports/full_pipeline_artifacts/sbert/sbert_similarity_head.pt` |
| NCF | `reports/full_pipeline_artifacts/ncf/online_ncf.json` |
| DQN checkpoint | `reports/full_pipeline_artifacts/dqn/dqn_model.pt` |
| DQN online state | `reports/full_pipeline_artifacts/dqn/online_dqn.json` |
| Retraining manifest | `reports/retraining_artifacts/retraining_manifest.json` |

## Fallback Behavior

- If live scraping fails, use `--skip-scraper` to run from the permanent sample dataset.
- If artifacts are missing, rerun `scripts/retrain_pipeline.py`.
- If SBERT transformer loading is too heavy for local/CI runs, use deterministic fallback embeddings.
- If API services are unstable during demo, run `scripts/run_full_pipeline.py` directly.
