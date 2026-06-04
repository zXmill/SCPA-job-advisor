# Evidence Gap for TA

Date: 2026-06-05

Scope: Phase 0 evidence audit for thesis defensibility. This file separates existing evidence, missing evidence, and claims that must remain conditional.

## Evidence Readiness Summary

| Evidence area | Existing evidence | Gap | Readiness |
|---|---|---|---|
| Dataset quality | Sample dataset validation and scraper quality reports exist | Need final dataset-quality report for actual TA dataset scale and provenance | Partial |
| SBERT fine-tuning | Fine-tuned checkpoint docs and metrics exist | Need retrieval metrics at Recall@50/100 and candidate-pool evidence | Partial |
| SBERT Recall@50/100 | Not found in required artifact layout | Must generate CSV/plots and error analysis | Missing |
| NCF interaction data | Sample interaction data and OnlineNCF exist | Need interaction summary, sparsity, real/synthetic labeling | Partial |
| DQN session adaptation gain | DQN metrics exist, but old skill-path objective dominates | Need before/after DQN rerank evidence from sessions | Missing |
| Ablation study | Some SBERT/NCF/DQN/hybrid rows exist | Need revised architecture ablation with consistent candidate pool and labels | Partial |
| Latency | Local p95 metrics exist | Need per-service breakdown and reproducible environment details | Partial |
| User testing/SUS | SUS target documented as missing | Need actual survey rows before any SUS claim | Missing |
| Plots and CSV outputs | Many report plots/CSVs exist | Required evidence directory layout is incomplete | Partial |
| Bab 4 and Bab 5 readiness | Current docs summarize sample/demo evidence | Need final evidence and limitations before thesis chapters | Not ready |

## 1. Dataset Quality

Existing evidence:

- `data/sample/` contains permanent sample users, jobs, interactions, and milestones.
- `scripts/sample_dataset.py` validates the sample dataset.
- `tests/test_sample_dataset_flow.py` asserts minimum sample counts and target checks.
- `reports/full_pipeline_summary.json` records 5 users, 9 sample jobs, 21 interactions, and 8 milestones.
- Continuous/live scraper evidence exists under `reports/debug/continuous_scrape/`.

Missing evidence:

- A final dataset provenance report separating sample jobs, live scraped jobs, manually curated jobs, synthetic rows, and generated rows.
- A final data quality CSV with counts for valid jobs, invalid jobs, duplicates, empty descriptions, missing skill evidence, missing source URLs, and source distribution.
- Proof for any "5,000 valid jobs" or similar dataset-size claim. Do not make that claim unless a data-quality report proves it.

Required next artifacts:

- `evidence/dataset/job_quality_summary.csv`
- `evidence/dataset/source_distribution.csv`
- `evidence/dataset/deduplication_report.csv`
- `docs/evaluation/DATASET_QUALITY_REPORT.md`

Claim boundary:

- Safe: "SCPA was validated on a small permanent sample dataset and selected live-scraper evidence."
- Unsafe: "SCPA proves large-scale Indonesian labor-market coverage" unless backed by a final dataset report.

## 2. SBERT Fine-Tuning

Existing evidence:

- `docs/MODELS.md` references active checkpoint `models/sbert-indonesian-hybrid-manual-research/best`.
- `services/sbert/main.py` can load a transformer model and reports fallback mode.
- `tests/test_sbert_finetuned_runtime.py` covers checkpoint loading without fallback.
- `reports/sbert_finetuning_hybrid/` contains baseline and evaluation artifacts.
- `CODE_REVIEW_SBERT_V2_RETRIEVAL_ALIGNMENT.md` identifies missing candidate-generator evidence.

Missing evidence:

- Retrieval-specific evidence that relevant jobs survive into Top-20, Top-50, and Top-100 candidate pools.
- Baseline comparison against lexical retrieval such as TF-IDF or BM25.
- Similarity distribution and error analysis.
- Explicit profile-level split and job-level holdout evidence.
- Hard-negative quality audit connected to final metrics.

Required next artifacts:

- `evidence/sbert/baseline_vs_finetuned.csv`
- `evidence/sbert/recall_at_k.csv`
- `evidence/sbert/ndcg_at_k.csv`
- `evidence/sbert/mrr_at_k.csv`
- `evidence/sbert/similarity_distribution.csv`
- `evidence/sbert/error_analysis.csv`
- `evidence/plots/sbert_baseline_vs_finetuned.png`
- `evidence/plots/sbert_recall_at_k_curve.png`
- `evidence/plots/sbert_ndcg_at_k_curve.png`
- `evidence/plots/sbert_similarity_distribution.png`

Claim boundary:

- Safe: "SBERT supports semantic matching and candidate scoring."
- Conditional: "Fine-tuned SBERT improves retrieval" only after retrieval metrics prove it.
- Unsafe: "SBERT alone is the final recommender" or "Top-5 results prove candidate-generation quality."

## 3. SBERT Recall@50/100

Existing evidence:

- Current docs mention NDCG@5 and Recall@5.
- Pipeline emits `sbert_score`.

Missing evidence:

- Recall@20, Recall@50, Recall@100.
- NDCG@10 and NDCG@50.
- MRR@10 and MAP@100.
- Top-N candidate retention analysis before NCF and DQN.

Required next artifacts:

- Same SBERT evidence files listed above, plus an explicit Top-N candidate-retention table.

Claim boundary:

- Do not claim SBERT is academically defensible as a Top-N generator until Recall@50/100 is produced.

## 4. NCF Interaction Data

Existing evidence:

- `services/ncf/main.py` implements OnlineNCF.
- `services/pipeline/stages/stage_3_ncf_score.py` calls NCF with candidate IDs and user/job context.
- `services/pipeline/main.py` sends feedback to NCF.
- `reports/full_pipeline_summary.json` and `reports/evaluation_metrics_summary.json` contain NCF metric rows.

Missing evidence:

- Interaction matrix sparsity.
- Number of distinct users, jobs, interactions by event type, and positive/negative labels.
- Clear label for whether interactions are real, simulated, seeded, or synthetic.
- Cold-start analysis.
- Contribution over SBERT-only baseline with enough interaction data.

Required next artifacts:

- `evidence/ncf/interaction_summary.csv`
- `evidence/ncf/matrix_sparsity.csv`
- `evidence/ncf/ncf_metrics.csv`
- `evidence/ncf/cold_start_analysis.csv`

Claim boundary:

- Safe: "NCF supports personalization when interaction history exists."
- Unsafe: "NCF is proven strong" if the only evidence remains 5 users and 21 sample interactions.

## 5. DQN Session Adaptation Gain

Existing evidence:

- `services/dqn/main.py` has DQN endpoints and reward update paths.
- `services/pipeline/stages/stage_4_dqn_rank.py` calls DQN `/rank`.
- `reports/full_pipeline_summary.json` has DQN metrics and career-path outputs.
- `reports/evaluation_metrics_summary.json` includes DQN job rerank and DQN action metrics.
- `CODE_REVIEW_DQN_V2_ALIGNMENT.md` documents DQN v2 alignment risks.

Missing evidence:

- DQN session-reranker output fields required by the revised contract.
- Rank before DQN and rank after DQN.
- Reward trace per session.
- NDCG@K before and after DQN reranking.
- Session Adaptation Gain = NDCG@K after DQN reranking - NDCG@K before DQN reranking.
- Clear separation of real sessions from simulation.

Required next artifacts:

- `evidence/dqn/session_adaptation_gain.csv`
- `evidence/dqn/reward_trace.csv`
- `evidence/dqn/rank_before_after.csv`
- `evidence/dqn/dqn_ablation.csv`
- `evidence/plots/dqn_session_adaptation_gain.png`
- `evidence/plots/dqn_reward_trend.png`
- `evidence/plots/dqn_rank_before_after.png`

Claim boundary:

- Safe: "DQN is intended to support intra-session reranking after alignment."
- Unsafe now: "DQN improves recommendation quality through session adaptation" without before/after DQN evidence.

## 6. Ablation Study

Existing evidence:

- `reports/full_pipeline_summary.json` contains rows for SBERT only, NCF only, DQN job rerank signal, and hybrid.
- `reports/evaluation_metrics_summary.json` contains notebook metric rows.
- `services/evaluation/ablation.py` exists.

Missing evidence:

- Required revised ablation set:
  - TF-IDF/BM25 baseline
  - Base SBERT
  - Fine-tuned SBERT
  - SBERT + NCF
  - SBERT + NCF + DQN
- Same candidate pool and evaluation split across variants.
- Statistical significance or confidence intervals if claims are strong.
- Honest report when a component does not improve results.

Required next artifacts:

- `evidence/ablation/model_comparison.csv`
- `evidence/plots/ablation_comparison.png`
- `docs/evaluation/ABLATION_REPORT.md`

Claim boundary:

- Safe: "The repo contains preliminary ablation-style sample metrics."
- Unsafe: "The full hybrid model is conclusively better" until required ablation is produced.

## 7. Latency

Existing evidence:

- `reports/full_pipeline_summary.json` contains p95 latency.
- `reports/evaluation_metrics_summary.json` contains p95 latency.
- `docs/EVALUATION.md` documents local latency limitations.
- Pipeline telemetry tests exist.

Missing evidence:

- Per-service latency distribution for SBERT, NCF, DQN, aggregation, gateway.
- P99 latency and environment description.
- Browser/API latency table for system evidence.

Required next artifacts:

- `evidence/system/latency_results.csv`
- `evidence/plots/latency_distribution.png`
- `evidence/plots/latency_breakdown.png`

Claim boundary:

- Safe: "Local smoke measurements met the configured p95 target."
- Unsafe: "Production latency is proven" without deployment-grade measurement.

## 8. User Testing and SUS

Existing evidence:

- `reports/evaluation_metrics_summary.json` says SUS is not computed because no survey rows exist.
- `docs/EVALUATION.md` repeats that SUS is not fabricated.
- `reports/thesis_evaluation_summary.md` documents SUS as missing.

Missing evidence:

- User survey responses.
- SUS scoring CSV.
- User feedback summary.
- Distribution plot.

Required next artifacts:

- `evidence/user_testing/sus_results.csv`
- `evidence/user_testing/user_feedback_summary.csv`
- `evidence/plots/sus_distribution.png`

Claim boundary:

- Safe: "SUS is a planned user-testing metric."
- Unsafe: "SUS target passed" without survey rows.

## 9. Plots and CSV Outputs

Existing evidence:

- Many generated PNGs and CSVs exist under `reports/`.
- `reports/evaluation_metrics_*.png` and `reports/evaluation_metrics_*.csv` exist.
- `notebooks/training_runs/readiness/` contains readiness figures.

Missing evidence:

- Required final evidence layout under `evidence/`.
- Source-to-claim mapping for each plot and CSV.
- Regeneration commands for every plot.

Required next artifacts:

- A canonical `evidence/` tree matching the Phase 3-7 requirements.
- `docs/evaluation/EVIDENCE_INDEX.md` mapping each thesis claim to exact evidence files.

## 10. Bab 4 and Bab 5 Readiness

Current status:

- Bab 4 is not ready for final claims because key evidence artifacts are missing.
- Bab 5 can already describe limitations: small sample data, proxy CTR, missing SUS, exploratory fairness, runtime DQN misalignment, and no Kubernetes production validation.

Needed before Bab 4:

- Final dataset-quality report.
- SBERT retrieval evidence.
- NCF interaction evidence.
- DQN session adaptation evidence.
- Revised ablation report.
- Latency and user-testing artifacts.

Needed before Bab 5:

- A limitations list tied to actual gaps, not generic disclaimers.
- Explicit separation between background motivation and measured claims.

## What Was Inspected

- `reports/full_pipeline_summary.json`
- `reports/evaluation_metrics_summary.json`
- `reports/thesis_evaluation_summary.md`
- `docs/EVALUATION.md`
- `docs/MODELS.md`
- `docs/THESIS_WRITING_NOTES.md`
- `services/evaluation/thesis_evaluation_protocol.py`
- `scripts/evaluate_sample_pipeline.py`
- `scripts/build_evaluation_metrics_notebook.py`
- `scripts/build_ml_readiness_notebook.py`
- SBERT, NCF, DQN, pipeline, and gateway runtime files

## What Was Changed

- This evidence gap report was created.
- No evidence-generation code was changed.
- No runtime code was changed.

## What Was Not Changed

- No metrics were recomputed.
- No plots were regenerated.
- No notebooks were executed.
- No generated report was overwritten.

## Commands Run

- Repository recovery commands listed in `docs/audit/PROJECT_STATE_AUDIT.md`.
- `rg` searches for DQN, learning-path, fallback/mock/synthetic, scoring, and evidence terms.
- Focused reads of reports, scripts, docs, and service files.

## Tests Run

No test suite was run for this audit-only phase.

## Remaining Risks

- Existing reports may still look stronger than the evidence allows.
- Old DQN learning-path outputs can contaminate thesis interpretation.
- The final thesis must not cite sample/demo metrics as production or national-scale results.
