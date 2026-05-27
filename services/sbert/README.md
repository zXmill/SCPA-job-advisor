# SCPA SBERT Service

This service scores semantic fit between one user profile and a list of job
descriptions. It exposes a small FastAPI API used by the pipeline orchestrator.

## Runtime design

The Docker runtime loads the fine-tuned Indonesian hybrid SBERT checkpoint from
`models/sbert-indonesian-hybrid-manual-research/best`. That checkpoint is the
`best` model produced by
`notebooks/03_sbert_fine_tuning_hybrid_research_manual_v3.ipynb`.

Serving uses `transformers` directly with SentenceTransformer-compatible mean
pooling and L2 normalization. This keeps inference on the same fine-tuned
weights while avoiding notebook/training-only imports in the service process.

The service still contains a deterministic fallback for local tests or offline
development when model weights are unavailable. It must be enabled explicitly
with `SBERT_FORCE_FALLBACK=1`; disabling transformer mode alone is treated as
an unhealthy production configuration.

Run the real model locally with:

```powershell
$env:SBERT_ENABLE_TRANSFORMER="1"
$env:SBERT_MODEL_LOADER="transformers"
$env:MODEL_DIR="E:\TUGAS AKHIR\SCPA\models\sbert-indonesian-hybrid-manual-research\best"
uvicorn main:app --host 0.0.0.0 --port 8002
```

When `MODEL_DIR` points to a populated local model directory, that path is used
before `MODEL_NAME`.

## Endpoints

### `GET /health`

Returns service status, fallback mode, loader backend, model version, model
path, artifact metadata, and embedding dimension.

### `POST /match/semantic`

Request:

```json
{
  "user_profile_text": "Sastra Inggris Public Speaking",
  "job_descriptions": ["Master of Ceremony", "Backend Developer"]
}
```

Response:

```json
{
  "scores": [
    {"job_index": 0, "score": 0.78, "job_text_preview": "Master of Ceremony"},
    {"job_index": 1, "score": 0.21, "job_text_preview": "Backend Developer"}
  ],
  "model_version": "sbert-indonesian-hybrid-manual-research-best",
  "model_name": "models/sbert-indonesian-hybrid-manual-research/best"
}
```

Scores are sorted descending. `job_index` maps each score back to the original
input list.

### `POST /encode`

Returns normalized embeddings for arbitrary text. The pipeline primarily uses
`/encode` so it can cache job embeddings and compute cosine similarity inside
stage 2. The response includes the active `model_version` for pipeline telemetry.

### `GET /metrics`

Returns lightweight operational metadata: embedding dimension, fallback mode,
cache TTL, model identifier, and latency mode.

## Encoding and scoring

Fallback encoding combines:

- normalized tokens from English and Indonesian profile/job text;
- semantic category activations for communication, language, events, software,
  data, business, and design;
- deterministic hashed token features to keep different texts distinct.

Fallback scoring combines category overlap, lexical overlap, and embedding
cosine similarity. It is intentionally deterministic so local tests can assert
domain behavior without relying on network downloads.

Important target behavior:

- `sbert_score("Sastra Inggris Public Speaking", "Master of Ceremony") > 0.6`
- `sbert_score("Sastra Inggris Public Speaking", "Backend Developer") < 0.4`

## Latency choices

- Docker/service runtime loads the fine-tuned checkpoint when
  `SBERT_ENABLE_TRANSFORMER=1`.
- `SBERT_MODEL_LOADER=transformers` is the supported serving backend.
- Text processing is linear in total input length.
- Redis embedding caching is optional and lazy; the service works without Redis.
- Deterministic fallback is opt-in through `SBERT_FORCE_FALLBACK=1`.

## Limitations

- The fallback is a deterministic approximation, not a learned semantic model.
- It is tuned for predictable local behavior and broad SCPA job categories.
- Current production/demo matching uses the fine-tuned SentenceTransformer
  checkpoint from `models/sbert-indonesian-hybrid-manual-research/best`.
- The service does not call or import the pipeline service.
