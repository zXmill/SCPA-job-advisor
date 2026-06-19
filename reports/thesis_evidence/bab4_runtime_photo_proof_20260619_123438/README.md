# BAB IV Runtime Photo Proof

Run ID: `20260619_123438`
Generated at: `2026-06-19T12:38:14+07:00`

This folder contains visual evidence that the SCPA program and model services were running locally during the capture. It is meant to answer the revision note that BAB IV needs real screenshots, not only textual proof.

## Main Evidence Images

Use these first in BAB IV:

- `screenshots/bab4_runtime_photo_contact_sheet.png` - one-page visual summary for frontend, SBERT, NCF, DQN, and inference responses.
- `screenshots/frontend_home_viewport.png` - frontend SCPA running at `http://127.0.0.1:3000`.
- `screenshots/sbert_health_browser.png` - SBERT `/health`, `model_loaded=true`, `fallback_mode=false`, `embedding_dim=384`.
- `screenshots/sbert_ready_browser.png` - SBERT `/ready`, real transformer checkpoint ready.
- `screenshots/ncf_health_browser.png` - NCF `/health`, `model_loaded=true`, `model_type=NeuMF`.
- `screenshots/dqn_health_browser.png` - DQN `/health`, `model_version=online-dqn-v2`.
- `screenshots/sbert_semantic_match_post.png` - SBERT semantic match response screenshot.
- `screenshots/ncf_recommend_post.png` - NCF recommendation response screenshot.
- `screenshots/dqn_rerank_post.png` - DQN session rerank response screenshot.

Terminal-style proof:

- `terminal/powershell_runtime_summary.png`
- `terminal/powershell_listening_ports.png`
- `terminal/powershell_docker_compose_blocker.png`

Raw auditable outputs:

- `raw/runtime_probe_summary.json`
- `raw/sbert_health.json`
- `raw/sbert_ready.json`
- `raw/sbert_semantic_match.json`
- `raw/sbert_encode.json`
- `raw/ncf_health.json`
- `raw/ncf_recommend.json`
- `raw/dqn_health.json`
- `raw/dqn_rerank.json`
- `raw/playwright_screenshot_summary.json`

## Runtime Facts From This Capture

- Frontend returned HTTP 200 at `http://127.0.0.1:3000`.
- SBERT returned `status=healthy`, `model_loaded=true`, `fallback_mode=false`, `embedding_dim=384`, checkpoint `a90605c4b3adbe95`.
- NCF returned `status=healthy`, `model_loaded=true`, `model_type=NeuMF`, `feedback_events=997`.
- DQN returned `status=healthy`, `model_version=online-dqn-v2`, `training_steps=606`.
- Inference probe returned SBERT top score `0.7304`, NCF top job `job-english-cs` score `0.734161`, and DQN top job `job-english-cs` score `0.630381` with policy `session_rerank`.

## Claim Boundary

Do not use this run as Docker Compose/database proof. `docker compose ps` failed because Docker Desktop was not running (`dockerDesktopLinuxEngine` pipe unavailable). This package proves local frontend plus SBERT/NCF/DQN service runtime and model inference, not current full Compose/database runtime.

## Suggested BAB IV Captions

- `Gambar 4.x Bukti antarmuka SCPA berjalan pada frontend lokal.`
- `Gambar 4.x Bukti runtime SBERT: model transformer termuat, fallback tidak aktif, dan dimensi embedding 384.`
- `Gambar 4.x Bukti runtime NCF: layanan NeuMF aktif dan menghasilkan skor rekomendasi.`
- `Gambar 4.x Bukti runtime DQN: session reranker aktif dan menghasilkan urutan ulang berdasarkan event sesi.`
- `Gambar 4.x Ringkasan visual bukti runtime program SCPA pada tanggal 19 Juni 2026.`
