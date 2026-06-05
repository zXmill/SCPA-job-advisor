"""Hybrid recommendation blending service (STALE / NOT ACTIVE).

WARNING: This standalone service is no longer part of the active runtime.
Active blending happens in services/pipeline/stages/stage_5_aggregate.py.
This file is retained only for backward compatibility and offline experiments.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import replace
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

try:
    from services.sbert.main import sbert_score
except Exception:  # pragma: no cover - only used if service import is broken
    sbert_score = None


FAIRNESS_TPR_THRESHOLD = 8.0
MODEL_VERSION = "hybrid-v2.0"


class CircuitBreaker:
    """Simple closed/open/half-open circuit breaker."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        name: str = "downstream",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_at: float | None = None

    def can_execute(self) -> bool:
        if self.state != "open":
            return True
        if self.last_failure_at is None:
            return False
        if (time.monotonic() - self.last_failure_at) >= self.recovery_timeout:
            self.state = "half_open"
            return True
        return False

    def record_success(self) -> None:
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_at = time.monotonic()
        if self.state == "half_open" or self.failure_count >= self.failure_threshold:
            self.state = "open"


class HybridScore(BaseModel):
    job_id: str
    hybrid_score: float
    sbert_score: float
    ncf_score: float
    alpha_used: float
    dqn_score: float = 0.0


class FairnessTracker:
    """Tracks true-positive rates and applies small disadvantaged-group boosts."""

    def __init__(self) -> None:
        self.tpr: dict[str, float] = {}
        self.counts: dict[str, dict[str, int]] = {}

    def update_stats(self, group: str, positive: bool) -> None:
        stats = self.counts.setdefault(group, {"positive": 0, "total": 0})
        stats["total"] += 1
        if positive:
            stats["positive"] += 1
        self.tpr[group] = stats["positive"] / max(stats["total"], 1)

    def get_tpr_gap(self) -> float:
        if len(self.tpr) < 2:
            return 0.0
        values = list(self.tpr.values())
        return (max(values) - min(values)) * 100.0

    def enforce_fairness(
        self,
        scores: list[HybridScore],
        user_group: str | None,
    ) -> list[HybridScore]:
        if not scores:
            return []
        gap = self.get_tpr_gap()
        if gap <= FAIRNESS_TPR_THRESHOLD or len(self.tpr) < 2:
            return scores
        disadvantaged = min(self.tpr, key=self.tpr.get)
        if user_group != disadvantaged:
            return scores
        boost = (gap - FAIRNESS_TPR_THRESHOLD) / 100.0
        boosted = [
            score.model_copy(
                update={"hybrid_score": min(1.0, score.hybrid_score + boost)}
            )
            for score in scores
        ]
        boosted.sort(key=lambda item: item.hybrid_score, reverse=True)
        return boosted


class HybridRequest(BaseModel):
    user_id: int | str
    user_profile_text: str = ""
    is_new_user: bool = False
    job_candidates: list[dict[str, Any]] = Field(default_factory=list)
    user_group: str | None = None
    top_k: int = Field(default=10, ge=0, le=100)


class HybridResponse(BaseModel):
    user_id: str
    recommendations: list[HybridScore]
    model_version: str = MODEL_VERSION
    reason: str = "ok"
    fairness_gap_pp: float = 0.0


app = FastAPI(title="SCPA Hybrid Recommendation Service", version="2.0.0")
ncf_circuit = CircuitBreaker(name="ncf")
sbert_circuit = CircuitBreaker(name="sbert")
fairness_tracker = FairnessTracker()


def _job_id(job: dict[str, Any], index: int) -> str:
    return str(job.get("id") or job.get("job_id") or f"job-{index}")


def _job_text(job: dict[str, Any]) -> str:
    raw_tags = job.get("tags") or []
    tags = " ".join(map(str, raw_tags)) if isinstance(raw_tags, list) else str(raw_tags)
    return " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "desc", "description")
    ) + f" {tags}"


def _stable_score(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return round(int.from_bytes(digest[:4], "big") / 0xFFFFFFFF, 6)


def _fallback_sbert(profile_text: str, job: dict[str, Any], index: int) -> float:
    text = _job_text(job)
    if sbert_score is not None:
        return float(sbert_score(profile_text, text))
    return _stable_score(profile_text.lower(), text.lower(), str(index))


def _fallback_dqn(job: dict[str, Any], sbert: float, ncf: float) -> float:
    prior = 0.55 * sbert + 0.35 * ncf
    return round(min(1.0, max(0.0, prior + 0.10 * _stable_score(_job_text(job)))), 6)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "hybrid",
        "model_version": MODEL_VERSION,
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "service": "hybrid",
        "metrics": {
            "ncf_circuit": ncf_circuit.state,
            "sbert_circuit": sbert_circuit.state,
            "fairness_gap_pp": round(fairness_tracker.get_tpr_gap(), 4),
            "fairness_threshold_pp": FAIRNESS_TPR_THRESHOLD,
        },
    }


@app.post("/recommend/hybrid", response_model=HybridResponse)
async def recommend_hybrid(request: HybridRequest) -> HybridResponse:
    candidates = request.job_candidates
    if not candidates:
        return HybridResponse(
            user_id=str(request.user_id),
            recommendations=[],
            reason="no_candidates",
            fairness_gap_pp=round(fairness_tracker.get_tpr_gap(), 4),
        )

    alpha = 1.0 if request.is_new_user else 0.5
    rows: list[HybridScore] = []
    for index, job in enumerate(candidates):
        job_id = _job_id(job, index)
        sbert = float(job.get("sbert_score") or _fallback_sbert(request.user_profile_text, job, index))
        ncf = float(job.get("ncf_score") or 0.0)
        dqn = float(job.get("dqn_score") or _fallback_dqn(job, sbert, ncf))
        hybrid = alpha * sbert + (1.0 - alpha) * ncf
        if "dqn_score" in job:
            hybrid = (0.60 * hybrid) + (0.40 * dqn)
        rows.append(
            HybridScore(
                job_id=job_id,
                hybrid_score=round(min(1.0, max(0.0, hybrid)), 6),
                sbert_score=round(min(1.0, max(0.0, sbert)), 6),
                ncf_score=round(min(1.0, max(0.0, ncf)), 6),
                dqn_score=round(min(1.0, max(0.0, dqn)), 6),
                alpha_used=alpha,
            )
        )

    rows.sort(key=lambda item: item.hybrid_score, reverse=True)
    rows = fairness_tracker.enforce_fairness(rows, request.user_group)
    top_k = request.top_k if request.top_k else len(rows)
    return HybridResponse(
        user_id=str(request.user_id),
        recommendations=rows[:top_k],
        fairness_gap_pp=round(fairness_tracker.get_tpr_gap(), 4),
    )

