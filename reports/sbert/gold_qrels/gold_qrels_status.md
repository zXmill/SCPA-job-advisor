# SBERT Gold Qrels Status

Status: `BLOCKED`

- Annotation rows: 744
- Silver judgements: 744 (`silver_qrels.csv`) — heuristic, not expert
- Gold judgements: 0 (`gold_qrels.csv`)
- Pending expert grade: 744 (`annotation_template.csv`)
- Inter-annotator agreement (linear-weighted Cohen's kappa): `None` (n/a, n=0)

## Adjudication decisions

- pending_no_grades: 744

## What can be claimed now

- Silver Precision@K / NDCG@K on the real fine-tuned SBERT.
- A reproducible adjudication + agreement pipeline (this script).

## What needs expert grades

- Expert-validated Precision@K / NDCG@K and a reported kappa.
- Next: two annotators fill `annotation_template.csv` (0-3), then re-run this script.
