# Thesis Dataset Clarity DOCX Update - 2026-06-19

## Status

Completed.

## Output

- `docs/thesis/bab4/BAB_IV_HASIL_DAN_PEMBAHASAN_DENGAN_SCRAPING_DATASET_JELAS.docx`

The previous output file `BAB_IV_HASIL_DAN_PEMBAHASAN_DENGAN_SCRAPING.docx` was open in Microsoft Word during generation, so the revised version was written to a new DOCX path instead of force-closing Word.

## Touched Files

- `scripts/thesis/insert_scraper_method_into_docx.py`
- `docs/thesis/bab4/BAB_IV_HASIL_DAN_PEMBAHASAN_DENGAN_SCRAPING_DATASET_JELAS.docx`
- `docs/agent/THESIS_DATASET_CLARITY_DOCX_20260619.md`

## Revision

Section `4.4.3 Dataset Interaksi Pengguna` now explicitly identifies:

- Main offline evaluation dataset: `simulated_grounded`.
- Main dataset directory: `data/eval/synthetic/`.
- Main dataset files: `interactions.jsonl`, `sessions.jsonl`, and `benchmark_metadata.json`.
- Dataset role: evaluation for NCF, DQN session reranker, and hybrid ablation.
- Interaction provenance: simulated click model with seed 42, grounded by real profile/job attributes.
- Positive events: `apply`, `save`, `click`, and `view_10s`.
- Size: 14.400 events, 300 synthetic users, 3.818 jobs, 900 sessions, positive_rate 0,4367.
- Runtime comparison dataset: `real_runtime` from table `feedback_events`.
- Runtime dataset directory: `data/eval/real_runtime/`.
- Runtime limitation: `insufficient_for_generalization` because 10 users is below the 30-user minimum threshold.

## Validation

- Generator syntax check passed:
  - `python.exe -m py_compile scripts\thesis\insert_scraper_method_into_docx.py`
- Structural DOCX check passed:
  - 212 paragraphs
  - 4 tables
  - 42 inline images
  - Required dataset strings found in the generated DOCX.
- LibreOffice renderer was unavailable in PATH; visual QA used Microsoft Word COM export plus Poppler rasterization.
- Visual QA passed:
  - 37 rendered pages.
  - Page 14 shows the start of section `4.4.3` and the `simulated_grounded` dataset definition.
  - Page 15 shows the grounding explanation, `real_runtime` comparison, and `Gambar 4.13`.
  - Existing user Word process remained open; only the temporary COM Word process was closed.

## Claim Boundary

The revised text states that `simulated_grounded` is not real-user click evidence. It is the main offline evaluation dataset because it has sufficient coverage for model evaluation, while `real_runtime` remains pilot/runtime evidence only.
