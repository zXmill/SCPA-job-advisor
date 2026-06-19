# THESIS BAB IV Runtime Photo Proof - 2026-06-19

## Status

Completed evidence capture for the user request: BAB IV needed real visual proof that the program runs, not only textual table entries.

## Output

- Evidence folder: `reports/thesis_evidence/bab4_runtime_photo_proof_20260619_123438/`
- Main contact sheet: `reports/thesis_evidence/bab4_runtime_photo_proof_20260619_123438/screenshots/bab4_runtime_photo_contact_sheet.png`
- Frontend screenshot: `reports/thesis_evidence/bab4_runtime_photo_proof_20260619_123438/screenshots/frontend_home_viewport.png`
- Runtime summary JSON: `reports/thesis_evidence/bab4_runtime_photo_proof_20260619_123438/raw/runtime_probe_summary.json`
- README with BAB IV caption guidance: `reports/thesis_evidence/bab4_runtime_photo_proof_20260619_123438/README.md`

## Runtime Validation

- Frontend dev server ran at `http://127.0.0.1:3000` and returned HTTP 200.
- SBERT ran at `http://127.0.0.1:8002`; `/health` returned `status=healthy`, `model_loaded=true`, `fallback_mode=false`, `embedding_dim=384`, checkpoint `a90605c4b3adbe95`.
- NCF ran at `http://127.0.0.1:8003`; `/health` returned `status=healthy`, `model_loaded=true`, `model_type=NeuMF`, `feedback_events=997`.
- DQN ran at `http://127.0.0.1:8004`; `/health` returned `status=healthy`, `model_version=online-dqn-v2`, `training_steps=606`.
- Inference probe called SBERT `/match/semantic`, NCF `/recommend/ncf`, and DQN `/rerank`.

## Important Boundary

Docker Compose/database runtime could not be refreshed in this run because Docker Desktop was not running. `docker compose ps` failed with missing `dockerDesktopLinuxEngine` pipe. The generated evidence proves local frontend and direct SBERT/NCF/DQN runtime/inference, not current Docker Compose or live database counts.
