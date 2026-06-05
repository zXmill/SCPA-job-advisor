# SCPA Gateway Service

## Role

The gateway is the public HTTP boundary for recommendations. It does not scrape
jobs, load model weights, run ranking logic, or touch the database. It forwards
requests to the pipeline service and adds lightweight latency headers for
observability.

## Endpoints

- `GET /health`: gateway liveness.
- `GET /ready`: calls `pipeline:/health`.
- `POST /pipeline/run`: forwards to `pipeline:/pipeline/run`.
- `POST /recommendations` and `POST /api/recommendations`: frontend aliases.

## Request

```json
{
  "user_id": 1,
  "refresh_jobs": false,
  "profile": {
    "program_studi": "Sastra Inggris",
    "jurusan": "Sastra Inggris",
    "skills": ["Bahasa Inggris", "Public Speaking"]
  },
  "interaction_count": 0,
  "limit": 20
}
```

## Latency

The gateway performs one async `httpx` call to the pipeline and does no local
model work. `X-Gateway-Latency-Ms` and `X-Gateway-P95-Target-Ms` are returned on
every response. The configured target is 150 ms p95 for local Docker traffic.

## Configuration

- `PIPELINE_URL` or `PIPELINE_SERVICE_URL`: default `http://pipeline:8005`
- `HTTP_TIMEOUT_SECONDS`: default `5`
- `HEALTH_TIMEOUT_SECONDS`: default `2`
- `GATEWAY_P95_TARGET_MS`: default `150`
