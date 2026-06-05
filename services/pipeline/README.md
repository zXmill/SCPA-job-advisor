# SCPA Pipeline Orchestrator

`services/pipeline` is the real-time ML lifecycle orchestrator. It owns no model
weights and imports no model-service code. It calls dedicated services over HTTP:

```text
Scrape -> Encode -> NCF Score -> DQN Rank -> Aggregate
```

## Continual Training

When `CONTINUAL_TRAINING_ENABLED=true`, the service starts a background loop:

1. Pull fresh scraped jobs from the scraper service.
2. Encode job text with SBERT.
3. Upsert job embeddings into the online NCF service.
4. Upsert job features into the online DQN reranker.
5. Repeat every `CONTINUAL_TRAINING_INTERVAL_SECONDS`.

Scraped jobs provide the item stream and feature updates. User preference labels
come from implicit feedback (`view`, `view_10s`, `click`, `apply`, `skip`).
This avoids pretending that scraping alone can reveal user preference.

## Endpoints

- `POST /pipeline/run`: run recommendation scoring for one user.
- `POST /feedback`: train NCF and DQN from one implicit feedback event.
- `GET /training/status`: inspect background training state.
- `POST /training/run-once`: manually run one scrape/embedding/upsert cycle.
- `GET /health`: liveness and downstream service configuration.

Example run:

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

Example feedback:

```json
{
  "user_id": 1,
  "job_id": "job-mc",
  "event": "click",
  "profile": {
    "program_studi": "Sastra Inggris",
    "skills": ["Bahasa Inggris", "Public Speaking"]
  },
  "job": {
    "id": "job-mc",
    "title": "Master of Ceremony",
    "description": "Host public events in English."
  }
}
```

## Aggregation

There is no static domain-map cap in the final ranker. The cold-start path uses
SBERT strongly; as interaction history grows, online NCF and DQN take over.

```text
final_score = (w_sbert * sbert_score) + (w_ncf * ncf_score) + (w_dqn * dqn_score)
```

| Segment | Interactions | SBERT | NCF | DQN |
| --- | ---: | ---: | ---: | ---: |
| Cold start | 0 | 0.7 | 0.2 | 0.1 |
| Warm | 1-20 | 0.4 | 0.3 | 0.3 |
| Active | >20 | 0.2 | 0.3 | 0.5 |

## Configuration

| Variable | Default |
| --- | --- |
| `SCRAPER_URL` | `http://scraper:8001` |
| `SBERT_URL` | `http://sbert:8002` |
| `NCF_URL` | `http://ncf:8003` |
| `DQN_URL` | `http://dqn:8004` |
| `HTTP_TIMEOUT_SECONDS` | `5` |
| `PIPELINE_JOB_LIMIT` | `20` |
| `CONTINUAL_TRAINING_ENABLED` | `true` |
| `CONTINUAL_TRAINING_INTERVAL_SECONDS` | `300` |
