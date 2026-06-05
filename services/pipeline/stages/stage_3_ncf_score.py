"""Stage 3: call NCF affinity scoring service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class NCFStageResult:
    jobs: list[dict[str, Any]]
    summary: dict[str, Any]


async def run_ncf_score_stage(
    client: httpx.AsyncClient,
    ncf_url: str,
    user: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> NCFStageResult:
    candidate_ids = [str(job["id"]) for job in jobs]
    payload = {
        "user_id": str(user["id"]),
        "n_items": len(candidate_ids),
        "profile_text": user.get("profile_text"),
        "interaction_count": int(user.get("interaction_count") or 0),
        "user_embedding": user.get("embedding"),
        "candidate_job_ids": candidate_ids,
        "candidates": [
            {
                "id": str(job["id"]),
                "title": job.get("title") or "",
                "description": job.get("embedding_text") or job.get("description_text") or job.get("description") or "",
                "tags": job.get("tags") or [],
                "embedding": job.get("embedding") or [],
                "sbert_score": float(job.get("sbert_score") or 0.0),
            }
            for job in jobs
        ],
    }
    response = await client.post(f"{ncf_url.rstrip('/')}/recommend/ncf", json=payload)
    response.raise_for_status()
    data = response.json()
    score_by_id = {
        str(item["job_id"]): float(item["score"])
        for item in data.get("recommendations", [])
    }
    enriched = [
        {**job, "ncf_score": score_by_id.get(str(job["id"]), 0.0)}
        for job in jobs
    ]
    return NCFStageResult(
        jobs=enriched,
        summary={
            "scored": len(score_by_id),
            "model_version": data.get("model_version"),
            "fallback_flags": [],
        },
    )
