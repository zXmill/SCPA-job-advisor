# A/B Testing and Monitoring Design (P4-ADV-004)

## Overview
Add lightweight A/B testing and monitoring infrastructure to the SCPA gateway so that recommendation variants can be compared in production using logged user behavior.

## Goals
- Run controlled experiments that assign users to recommendation variants.
- Log impressions and conversions per variant.
- Compute engagement metrics (CTR proxy, apply rate, dwell time) per variant.
- Surface a monitoring dashboard endpoint with live experiment status.

## Non-Goals
- Full multi-armed bandit optimization (out of scope).
- Real-time p-value computation on every request.

## Architecture

### Database Layer
Three new tables:

1. **experiments**
   - `id` (UUID PK)
   - `name` (unique, human-readable)
   - `description` (text)
   - `variants` (JSONB list of variant objects: `{name, config, weight}`)
   - `status` (`draft`, `running`, `paused`, `completed`)
   - `start_at`, `end_at` (timestamps, nullable)
   - `target_metric` (e.g., `click_through_rate`, `apply_rate`)
   - `created_at`, `updated_at`

2. **experiment_assignments**
   - `id` (BIGINT PK)
   - `experiment_id` (FK -> experiments.id)
   - `user_id` (FK -> users.id, nullable for anonymous)
   - `variant_name` (string, matches a variant in the experiment)
   - `assigned_at` (timestamp)
   - Unique constraint on `(experiment_id, user_id)`

3. **experiment_metrics**
   - `id` (BIGINT PK)
   - `experiment_id` (FK -> experiments.id)
   - `variant_name` (string)
   - `metric_name` (string)
   - `value` (float)
   - `sample_size` (int)
   - `computed_at` (timestamp)

### Assignment Strategy
Deterministic hash-based assignment using `hash(user_id + experiment_id) % 100` mapped to variant weights. This ensures:
- Same user always gets the same variant for a given experiment.
- No state needed at assignment time beyond the assignment row itself.
- Easy to backfill from logs.

### Gateway Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/experiments` | Create a new experiment |
| GET | `/api/experiments` | List experiments |
| GET | `/api/experiments/{id}` | Get experiment detail |
| POST | `/api/experiments/{id}/start` | Start an experiment |
| POST | `/api/experiments/{id}/pause` | Pause an experiment |
| POST | `/api/experiments/{id}/complete` | Complete an experiment |
| POST | `/api/experiments/{id}/assign` | Assign a user to a variant |
| GET | `/api/experiments/{id}/metrics` | Get aggregated metrics |
| POST | `/api/events/track` | Track a conversion/engagement event tied to an experiment variant |

### Event Tracking
The existing `/api/recommendations/feedback` endpoint logs `feedback_events`. For A/B testing, we also track:
- `experiment_id` and `variant_name` in `feedback_events.model_provenance` when the recommendation was served under an experiment.
- A dedicated `POST /api/events/track` for explicit conversion events (apply, save, share) tied to an experiment assignment.

### Metrics Computation
A background-friendly endpoint `GET /api/experiments/{id}/metrics` computes:
- **CTR proxy**: clicks / impressions per variant
- **Apply rate**: apply events / impressions per variant
- **Mean dwell time**: average dwell_ms per variant
- **Sample size**: number of users assigned per variant

These are computed on-demand from `feedback_events` and `experiment_assignments` rather than maintained in real-time counters, to keep the implementation simple and auditable.

## Smoke Implementation Scope
For this task:
1. Create the three tables via Alembic migration.
2. Add gateway CRUD endpoints for experiments.
3. Add hash-based assignment endpoint.
4. Add lightweight metrics aggregation endpoint.
5. Add event tracking endpoint.
6. Wire experiment variant into the recommendation `model_provenance` when an active experiment is configured.
7. Tests covering all new endpoints.

## Future Work
- Scheduled metrics pre-computation.
- Automated significance testing using `services/evaluation/significance.py`.
- Bandit-style auto-allocation.
