"""Stage 4: adapt the DQN runtime into the TA session-reranker contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


ALLOWED_DQN_MODES = {
    "session_rerank",
    "disabled_cold_start",
    "fallback_no_session_events",
}


@dataclass
class DQNStageResult:
    jobs: list[dict[str, Any]]
    summary: dict[str, Any]


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _session_events(user: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("session_events", "session_history", "interaction_history", "recent_interactions"):
        value = user.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [item for item in value.values() if isinstance(item, dict)]
    return []


def _pre_dqn_score(job: dict[str, Any]) -> float:
    return (0.6 * _clamp01(job.get("sbert_score"))) + (0.4 * _clamp01(job.get("ncf_score")))


def _lineage_for(job: dict[str, Any]) -> dict[str, str]:
    return {
        "stage_2": "sbert_semantic_candidate_generator",
        "stage_2_candidate_pool": str(job.get("candidate_pool_source") or "sbert_top_m"),
        "stage_3": "ncf_interaction_reranker" if "ncf_score" in job else "ncf_not_scored",
        "stage_4": "dqn_session_reranker",
    }


def _rank_before_dqn(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(jobs, key=_pre_dqn_score, reverse=True)
    return [
        {
            **job,
            "rank_before_dqn": index,
            "candidate_pool_source": _lineage_for(job),
        }
        for index, job in enumerate(ranked, start=1)
    ]


def _fallback_jobs(jobs: list[dict[str, Any]], *, mode: str, reason: str) -> list[dict[str, Any]]:
    ranked = _rank_before_dqn(jobs)
    return [
        {
            **job,
            "rank_after_dqn": index,
            "dqn_session_score": 0.0,
            "dqn_score": 0.0,
            "dqn_mode": mode,
            "reward_trace": {
                "status": "not_computed",
                "reason": reason,
            },
        }
        for index, job in enumerate(ranked, start=1)
    ]


def _ranked_job_id(item: dict[str, Any]) -> str:
    job = item.get("job") if isinstance(item.get("job"), dict) else {}
    return str(
        item.get("job_id")
        or item.get("id")
        or job.get("job_id")
        or job.get("id")
        or ""
    )


def _score_from_ranked_item(item: dict[str, Any], q_min: float, q_max: float) -> float:
    for key in ("dqn_session_score", "session_score", "score", "final_score"):
        if key in item:
            return _clamp01(item.get(key))
    q_value = float(item.get("q_value", 0.0))
    if q_max > q_min:
        return _clamp01((q_value - q_min) / (q_max - q_min))
    return _clamp01(q_value)


def _reward_trace(item: dict[str, Any]) -> Any:
    if "reward_trace" in item:
        return item.get("reward_trace")
    if "reward_components" in item:
        return {
            "source": "dqn_reward_components",
            "components": item.get("reward_components"),
        }
    return {"status": "not_returned_by_dqn_service"}


async def run_dqn_rank_stage(
    client: httpx.AsyncClient,
    dqn_url: str,
    user: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> DQNStageResult:
    if not jobs:
        return DQNStageResult(
            jobs=[],
            summary={
                "ranked": 0,
                "dqn_mode": "fallback_no_session_events",
                "dqn_modes": ["fallback_no_session_events"],
                "reason": "empty_candidate_pool",
                "session_event_count": 0,
            },
        )

    session_events = _session_events(user)
    interaction_count = int(user.get("interaction_count") or 0)
    if not session_events:
        mode = "disabled_cold_start" if interaction_count <= 0 else "fallback_no_session_events"
        reason = (
            "cold_start_without_session_events"
            if mode == "disabled_cold_start"
            else "missing_session_events"
        )
        fallback = _fallback_jobs(jobs, mode=mode, reason=reason)
        return DQNStageResult(
            jobs=fallback,
            summary={
                "ranked": len(fallback),
                "dqn_mode": mode,
                "dqn_modes": [mode],
                "reason": reason,
                "candidate_pool_source": "sbert_ncf_top_m",
                "session_event_count": 0,
            },
        )

    pre_ranked_jobs = _rank_before_dqn(jobs)
    candidates = [
        {
            "id": str(job["id"]),
            "job_id": str(job.get("job_id") or job["id"]),
            "title": job.get("title"),
            "company": job.get("company"),
            "description": job.get("embedding_text") or job.get("description_text") or job.get("description"),
            "tags": job.get("tags", []),
            "skills": job.get("skills", []),
            "embedding": job.get("embedding", []),
            "base_score": job.get("sbert_score", 0.0),
            "sbert_score": job.get("sbert_score", 0.0),
            "ncf_score": job.get("ncf_score", 0.0),
            "rank_before_dqn": job["rank_before_dqn"],
            "candidate_pool_source": job["candidate_pool_source"],
        }
        for job in pre_ranked_jobs
    ]
    payload = {
        "user_id": str(user["id"]),
        "session_id": str(user.get("session_id") or ""),
        # canonical contract: ask DQN with session_events
        "session_events": session_events,
        # session_history is intentionally not sent as a separate active top-level DQN field
        "session_ctx": {
            "skills": user.get("skills", []),
            "target_role": user.get("target_role") or user.get("program_studi") or user.get("jurusan"),
            "interaction_count": interaction_count,
            "profile_text": user.get("profile_text"),
            "interaction_history": session_events,
            "session_events": session_events,
            "reranker_contract": "session_rerank_v1",
        },
        "candidates": candidates,
        "job_candidates": candidates,
        "top_k": len(candidates),
    }
    response = await client.post(f"{dqn_url.rstrip('/')}/rerank", json=payload)
    response.raise_for_status()
    data = response.json()
    ranked_items = data.get("ranked_jobs") or data.get("ranked", [])
    q_values = [float(item.get("q_value", 0.0)) for item in ranked_items]
    q_min = min(q_values) if q_values else 0.0
    q_max = max(q_values) if q_values else 0.0
    score_by_id: dict[str, float] = {}
    metadata_by_id: dict[str, dict[str, Any]] = {}
    after_rank_by_id: dict[str, int] = {}
    for rank_after, item in enumerate(ranked_items, start=1):
        job_id = _ranked_job_id(item)
        if not job_id:
            continue
        q_value = float(item.get("q_value", 0.0))
        score = _score_from_ranked_item(item, q_min, q_max)
        mode = str(item.get("dqn_mode") or data.get("dqn_mode") or "session_rerank")
        if mode not in ALLOWED_DQN_MODES:
            mode = "session_rerank"
        score_by_id[job_id] = round(score, 6)
        after_rank_by_id[job_id] = rank_after
        metadata_by_id[job_id] = {
            "dqn_session_score": round(score, 6),
            "dqn_q_value": round(q_value, 6),
            "dqn_action": item.get("action"),
            "dqn_action_label": item.get("action_label"),
            "dqn_action_type": item.get("action_type"),
            "dqn_rerank_reason": item.get("rerank_reason"),
            "dqn_policy_source": item.get("policy_source"),
            "dqn_policy_objective": item.get("policy_objective") or data.get("policy_objective"),
            "reward_trace": _reward_trace(item),
            "dqn_mode": mode,
        }

    enriched = []
    for job in pre_ranked_jobs:
        job_id = str(job.get("job_id") or job["id"])
        score = score_by_id.get(job_id, 0.0)
        enriched.append(
            {
                **job,
                "rank_after_dqn": after_rank_by_id.get(job_id, job["rank_before_dqn"]),
                "dqn_session_score": score,
                "dqn_score": score,
                "reward_trace": {"status": "not_returned_by_dqn_service"},
                "dqn_mode": "session_rerank",
                **metadata_by_id.get(job_id, {}),
            }
        )
    enriched.sort(
        key=lambda job: (
            int(job.get("rank_after_dqn") or 10**9),
            int(job.get("rank_before_dqn") or 10**9),
        )
    )
    modes = sorted({str(job.get("dqn_mode")) for job in enriched if job.get("dqn_mode")})
    return DQNStageResult(
        jobs=enriched,
        summary={
            "ranked": len(score_by_id),
            "reason": data.get("reason"),
            "model_version": (data.get("metadata") or {}).get("model_version") or data.get("model_version"),
            "dqn_mode": modes[0] if len(modes) == 1 else "session_rerank",
            "dqn_modes": modes,
            "policy_objective": data.get("policy_objective"),
            "policy_sources": sorted(
                {
                    str(item.get("dqn_policy_source"))
                    for item in metadata_by_id.values()
                    if item.get("dqn_policy_source")
                }
            ),
            "candidate_pool_source": "sbert_ncf_top_m",
            "session_event_count": len(session_events),
            "rerank_reasons": sorted(
                {
                    str(item.get("dqn_rerank_reason"))
                    for item in metadata_by_id.values()
                    if item.get("dqn_rerank_reason")
                }
            ),
        },
    )
