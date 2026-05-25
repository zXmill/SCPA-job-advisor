"""Stage 4: call DQN ranker service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class DQNStageResult:
    jobs: list[dict[str, Any]]
    summary: dict[str, Any]


async def run_dqn_rank_stage(
    client: httpx.AsyncClient,
    dqn_url: str,
    user: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> DQNStageResult:
    candidates = [
        {
            "id": str(job["id"]),
            "title": job.get("title"),
            "company": job.get("company"),
            "description": job.get("description"),
            "tags": job.get("tags", []),
            "embedding": job.get("embedding", []),
            "sbert_score": job.get("sbert_score", 0.0),
            "ncf_score": job.get("ncf_score", 0.0),
        }
        for job in jobs
    ]
    payload = {
        "user_id": str(user["id"]),
        "job_candidates": candidates,
        "session_ctx": {
            "skills": user.get("skills", []),
            "target_role": user.get("target_role") or user.get("program_studi") or user.get("jurusan"),
            "interaction_count": int(user.get("interaction_count") or 0),
            "profile_text": user.get("profile_text"),
            "interaction_history": [],
        },
    }
    response = await client.post(f"{dqn_url.rstrip('/')}/rank", json=payload)
    response.raise_for_status()
    data = response.json()
    ranked_items = data.get("ranked", [])
    q_values = [float(item.get("q_value", 0.0)) for item in ranked_items]
    q_min = min(q_values) if q_values else 0.0
    q_max = max(q_values) if q_values else 0.0
    score_by_id: dict[str, float] = {}
    metadata_by_id: dict[str, dict[str, Any]] = {}
    for item in ranked_items:
        job = item.get("job") or {}
        q_value = float(item.get("q_value", 0.0))
        score = (q_value - q_min) / (q_max - q_min) if q_max > q_min else q_value
        job_id = str(job.get("id"))
        score_by_id[job_id] = round(score, 6)
        metadata_by_id[job_id] = {
            "dqn_q_value": round(q_value, 6),
            "dqn_action": item.get("action"),
            "dqn_action_label": item.get("action_label"),
            "dqn_action_type": item.get("action_type"),
            "dqn_policy_source": item.get("policy_source"),
            "dqn_policy_objective": item.get("policy_objective"),
            "dqn_reward_components": item.get("reward_components"),
            "dqn_skill_gap": item.get("skill_gap"),
            "dqn_estimated_skill_gap_after": item.get("estimated_skill_gap_after"),
            "dqn_market_demand": item.get("market_demand"),
        }

    enriched = [
        {
            **job,
            "dqn_score": score_by_id.get(str(job["id"]), 0.0),
            **metadata_by_id.get(str(job["id"]), {}),
        }
        for job in jobs
    ]
    return DQNStageResult(
        jobs=enriched,
        summary={
            "ranked": len(score_by_id),
            "reason": data.get("reason"),
            "model_version": data.get("model_version"),
            "policy_objective": next(
                (
                    str(item.get("dqn_policy_objective"))
                    for item in metadata_by_id.values()
                    if item.get("dqn_policy_objective")
                ),
                None,
            ),
            "policy_sources": sorted(
                {
                    str(item.get("dqn_policy_source"))
                    for item in metadata_by_id.values()
                    if item.get("dqn_policy_source")
                }
            ),
            "actions": sorted(
                {
                    str(item.get("dqn_action_label"))
                    for item in metadata_by_id.values()
                    if item.get("dqn_action_label")
                }
            ),
        },
    )
