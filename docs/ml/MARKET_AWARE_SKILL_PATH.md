# Market-Aware Skill Path Recommender Design

## Objective
Inject real-time market demand signals into the DQN learning path so users are guided toward skills that are both relevant to their target role and in high demand among current job postings.

## Background
The DQN service already accepts a `market_demand: dict[str, float]` parameter in its `LearningPathRequest` and uses it in `build_skill_path_state`, `_market_demand_for_skill`, and the step ranking logic. However, the gateway's `/api/learning-path` endpoint never populates or passes this field, so the DQN falls back to a default `0.5` demand for every skill.

## In-Scope (Smoke)
- Compute market demand from the existing `job_required_skills` + `skills` tables in the gateway.
- Pass computed demand to the DQN `/learning-path` endpoint.
- Return demand data alongside the learning path steps so the frontend can display it.
- Add `GET /api/market-demand` endpoint for standalone market-data queries.
- Add tests for market-demand computation and learning path integration.

## Out-of-Scope (Future)
- Trend forecasting (week-over-week demand changes).
- Salary-weighted demand (higher-paying jobs = higher demand weight).
- Location-filtered demand (Jakarta-only vs remote).
- Real-time streaming demand updates.

## Architecture

```
User requests /api/learning-path
        |
        v
Gateway
  - Fetch user skills
  - Compute market demand: COUNT(job_required_skills) per skill, normalized [0,1]
  - Call DQN /learning-path with market_demand
  - Return steps + market_demand

User requests GET /api/market-demand
        |
        v
Gateway
  - Compute market demand (same helper)
  - Return top-N skills with demand scores
```

## Market Demand Computation

SQL:
```sql
SELECT s.name, COUNT(*) AS job_count
FROM job_required_skills jrs
JOIN skills s ON jrs.skill_id = s.id
GROUP BY s.name
```

Normalization:
- `max_count = MAX(job_count)` across all skills.
- `demand = job_count / max_count` (clamped to [0, 1]).
- If no skills exist in the join table, return an empty dict (DQN falls back to defaults).

## API Contracts

### `POST /api/learning-path` (updated)
Request: same as before (auth only).

Response (updated):
```json
{
  "steps": [
    {
      "skill": "Python",
      "priority": 1,
      "estimated_weeks": 4,
      "resources": ["..."],
      "market_demand": 0.92
    }
  ],
  "estimated_months": 6,
  "market_demand": {
    "Python": 0.92,
    "SQL": 0.78,
    "Docker": 0.65
  }
}
```

### `GET /api/market-demand`
Request: authenticated.

Response:
```json
{
  "skills": [
    {"skill": "Python", "demand": 0.92, "job_count": 120},
    {"skill": "SQL", "demand": 0.78, "job_count": 102}
  ],
  "total_skills": 45,
  "computed_at": "2026-05-26T01:45:00+00:00"
}
```

## Implementation Plan
1. Add `_compute_skill_market_demand(db)` helper in gateway.
2. Update `/api/learning-path` to call the helper and forward demand to DQN.
3. Add `GET /api/market-demand` endpoint.
4. Write `tests/test_market_aware_skill_path.py`.

## Validation
- Focused pytest for market-demand computation.
- Full backend pytest regression.
