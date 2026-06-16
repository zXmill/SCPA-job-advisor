# Thesis BAB IV Visual Proof Report

Date: 2026-06-16

## Scope

This pass strengthens BAB IV evidence presentation for the SCPA thesis. The work
does not modify production runtime services, model weights, database migrations,
or frontend source code. It only creates visual evidence assets, a notebook
index, and a revised DOCX deliverable.

## Generated Deliverables

- Final DOCX:
  `C:\Users\ACER\Downloads\Penelitian\TA\IMPLEMENTASI HYBRID MODEL COLLABORATIVE FILTERING - BAB IV SCPA Full Final + Visual Proof Max.docx`
- Visual evidence run:
  `reports/thesis_evidence/bab4_visual_proof_20260616_231552/`
- Latest visual manifest:
  `reports/thesis_evidence/bab4_visual_proof_latest.json`
- Notebook index:
  `notebooks/thesis/07_bab4_visual_proof_evidence.ipynb`
- Mermaid source:
  `reports/thesis_evidence/bab4_visual_proof_20260616_231552/mermaid/bab4_runtime_recommendation_flow.mmd`
- Rendered QA PDF:
  `tmp/render_visual_proof_max_word_v2/BAB_IV_SCPA_Full_Final_Visual_Proof_Max.pdf`

## What Changed

- Added a new BAB IV section: `4.19 Validasi Visual Evidence Maksimal BAB IV`.
- Added visual evidence cards for SBERT, NCF, DQN, and hybrid ablation/claim
  boundaries.
- Added runtime/benchmark dashboard, qrels status plot, DQN session delta plots,
  frontend/API screenshots, PowerShell-style terminal evidence, and Mermaid
  source screenshot.
- Converted all 50 Word tables in the generated DOCX output into PNG images, so
  the final DOCX has `tables=0` and `inline_shapes=103`.
- Cropped full-page Playwright screenshots into DOCX-friendly top evidence crops
  while keeping the full screenshots in the evidence folder for audit.

## Evidence Sources

- Runtime evidence:
  `reports/thesis_evidence/bab4_runtime_evidence_latest.json`
- Benchmark/frozen split evidence:
  `reports/thesis_evidence/bab4_benchmark_evidence_latest.json`
- Qrels status:
  `reports/sbert/gold_qrels/gold_qrels_status.json`
- Source contracts:
  `services/sbert/main.py`, `services/shared/job_text.py`,
  `services/ncf/main.py`, `services/dqn/main.py`,
  `services/evaluation/model_rankers.py`.

## Validation

- Asset builder executed successfully with repo `.venv`.
- DOCX insertion/conversion executed successfully with bundled Python plus repo
  `.venv` plotting packages.
- Structural DOCX audit:
  - size: 24,546,302 bytes
  - paragraphs: 1,029
  - Word tables: 0
  - inline shapes: 103
  - section 4.19 found before `DAFTAR PUSTAKA BAB IV`
- Word COM export succeeded:
  - final rendered PDF pages: 127
  - rendered PNG pages: 127
- Visual QA inspected:
  - contact sheet for last 40 pages
  - pages 121-126 for frontend/API/terminal/mermaid section
  - no blank heading-only page after the screenshot crop fix
  - no visible clipping/overlap on inspected pages

## Claim Boundaries Kept

- Frontend screenshots prove artifact operability at documented capture time,
  not usability satisfaction.
- Benchmark metrics are `simulated_grounded`, derived from real profile/job
  attributes, not real production-user behavior.
- SBERT expert Precision/NDCG/MAP remains blocked until gold qrels and
  inter-annotator agreement exist.
- DQN is documented as session reranking only, not a learning-path model.

