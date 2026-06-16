# Thesis BAB IV Evidence Notebooks Report

Status: completed
Started: 2026-06-16
Completed: 2026-06-16

## Scope

Create a non-runtime evidence package for BAB IV:

- notebook evidence that can be executed and screenshotted,
- Matplotlib evidence tables/plots for split-status style figures,
- terminal/PowerShell-style database and command screenshots,
- frontend screenshots from the running system when available,
- explicit placeholders for scientific evidence that still needs expert labels or user-study data.

## Constraints

- Do not modify recommendation runtime behavior.
- Do not fabricate qrels, personalization, reward, usability, fairness, or production-scale claims.
- Evidence already present in the system should be extracted into screenshot-ready artifacts.
- Missing scientific evidence should be marked as placeholder or blocked, not silently treated as available.

## Output

Primary run directory:

- `reports/thesis_evidence/bab4_runtime_evidence_20260616_191943`

Notebook outputs:

- `notebooks/thesis/05_bab4_runtime_evidence_capture.ipynb`
- `reports/thesis_evidence/bab4_runtime_evidence_20260616_191943/executed_notebooks/05_bab4_runtime_evidence_capture.executed.ipynb`

Screenshot-ready evidence:

- `plots/status_split_eksperimen.png`
- `plots/model_runtime_evidence_matrix.png`
- `plots/model_evidence_status_bar.png`
- `plots/database_embedding_coverage.png`
- `plots/database_sources.png`
- `plots/dqn_rank_before_after.png`
- `plots/frontend_api_recommendation_summary.png`
- `terminal_screens/powershell_database_counts.png`
- `terminal_screens/powershell_docker_compose_ps.png`
- `terminal_screens/powershell_frontend_playwright.png`
- `terminal_screens/powershell_dqn_rerank.png`
- `screenshots/frontend_recommendations_initial_live.png`
- `screenshots/frontend_recommendations_after_events_live.png`
- `screenshots/frontend_model_panel_live.png`
- `screenshots/placeholder_expert_qrels_needed.png`
- `screenshots/placeholder_user_study_needed.png`

## Validation

- Frontend live capture succeeded from `http://localhost:3000`.
- Gateway live health returned 200 from `http://localhost:9000/health`.
- `docker compose ps` showed core services running and healthy at capture time.
- PostgreSQL evidence was collected via `docker compose exec -T postgres psql`.
- Notebook execution status: executed true, error null.
- Executed notebook contains 8 executed code cells and 16 image outputs.

## BAB IV DOCX Integration

Integrated into BAB IV DOCX:

- Source DOCX preserved: `C:\Users\ACER\Downloads\Penelitian\TA\IMPLEMENTASI HYBRID MODEL COLLABORATIVE FILTERING - BAB IV SCPA Full Final.docx`
- New DOCX: `C:\Users\ACER\Downloads\Penelitian\TA\IMPLEMENTASI HYBRID MODEL COLLABORATIVE FILTERING - BAB IV SCPA Full Final + Evidence.docx`
- Insert location: before `DAFTAR PUSTAKA BAB IV`
- New subchapter: `4.17 Validasi Runtime Sistem dan Bukti Hasil Notebook`
- Added tables: `Tabel 4.40` through `Tabel 4.42`
- Added figures: `Gambar 4.7` through `Gambar 4.22`
- Rendered PDF pages: 113 A5 pages
- Render QA focus: pages 102-113, covering the inserted evidence section and the bibliography transition.

## Runtime Facts Captured

- `active_accepted_jobs`: 8328
- `total_jobs`: 16645
- `ready_embeddings`: 16644
- `embedding_dimension`: 384
- `embedding_model_version`: `sbert-indonesian-hybrid-manual-research-best`
- active accepted job sources: jobstreet 3433, glints 2847, linkedin 1957, kalibrr 91

## Blocked or Placeholder Evidence

- Expert qrels are not completed, so expert-labeled Precision/NDCG/MAP must not be claimed.
- NCF temporal/user holdout still needs real event split validation.
- DQN reward split/general reward metric still needs session trajectory validation.
- Hybrid ablation still needs same-data/same-qrels comparison before superiority claims.
- Usability/SUS and fairness claims need separate real user-study/audit data.

## Follow-up Benchmark Completion

Completed on 2026-06-16 in `docs/agent/THESIS_BENCHMARK_CONTINUATION_REPORT.md`.

- Added evaluation-only fix: synthetic benchmark timestamps now use `interleaved_user_waves`, so temporal split evaluates returning users rather than generator-order user batches.
- Regenerated full benchmark: 300 users, 3,818 jobs, 14,400 interactions, 900 sessions.
- Temporal split now has 135 scored test users and `cold_users_in_test=0`.
- Session split is available: 630 train / 135 validation / 135 test sessions, overlap 0.
- Hybrid ablation is available on the same benchmark: temporal full_scpa NDCG@10 0.6943; user-holdout full_scpa NDCG@10 0.5971.
- DQN multi-seed stability is available with CV 0.004274.
- DQN held-out session proxy is available with 135 sessions, 2,160 event rows, mean delta NDCG@10 0.003714, and mean positive delta rank -0.032009.
- SBERT qrels status is explicit: 744 silver judgements, 0 gold judgements, 744 pending expert grades, kappa null.
- New notebook: `notebooks/thesis/06_thesis_benchmark_evaluation.ipynb`.
- New DOCX: `C:\Users\ACER\Downloads\Penelitian\TA\IMPLEMENTASI HYBRID MODEL COLLABORATIVE FILTERING - BAB IV SCPA Full Final + Evidence + Benchmark + DQN Proxy.docx`.
