"""HTTP-only ML lifecycle orchestrator for SCPA.

This service owns no model weights and imports no model service code. A pipeline
run calls scraper, SBERT, NCF, DQN, then aggregates the returned scores.
"""

from __future__ import annotations

import logging
import math
import os
import time
import asyncio
import hmac
import uuid
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .stages.stage_1_scrape import JOB_CACHE, run_scrape_stage
    from .stages.stage_2_encode import run_encode_stage
    from .stages.stage_3_ncf_score import run_ncf_score_stage
    from .stages.stage_4_dqn_rank import run_dqn_rank_stage
    from .stages.stage_5_aggregate import run_aggregate_stage
except ImportError:  # pragma: no cover - used when running from services/pipeline
    from stages.stage_1_scrape import JOB_CACHE, run_scrape_stage
    from stages.stage_2_encode import run_encode_stage
    from stages.stage_3_ncf_score import run_ncf_score_stage
    from stages.stage_4_dqn_rank import run_dqn_rank_stage
    from stages.stage_5_aggregate import run_aggregate_stage


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("scpa.pipeline")

SCRAPER_URL = os.getenv("SCRAPER_URL", os.getenv("SCRAPER_SERVICE_URL", "http://scraper:8001")).rstrip("/")
SBERT_URL = os.getenv("SBERT_URL", os.getenv("SBERT_SERVICE_URL", "http://sbert:8002")).rstrip("/")
NCF_URL = os.getenv("NCF_URL", os.getenv("NCF_SERVICE_URL", "http://ncf:8003")).rstrip("/")
DQN_URL = os.getenv("DQN_URL", os.getenv("DQN_SERVICE_URL", "http://dqn:8004")).rstrip("/")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
INTERNAL_SERVICE_TOKEN_HEADER = "X-Internal-Service-Token"
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))
DEFAULT_JOB_LIMIT = int(os.getenv("PIPELINE_JOB_LIMIT", "20"))
CANDIDATE_POOL_LIMIT = int(os.getenv("PIPELINE_CANDIDATE_POOL_LIMIT", "250"))
SCRAPE_TARGET = int(os.getenv("JOBS_TARGET", "2000"))
P95_TARGET_MS = int(os.getenv("PIPELINE_P95_TARGET_MS", "150"))
CONTINUAL_TRAINING_ENABLED = os.getenv("CONTINUAL_TRAINING_ENABLED", "true").lower() in {"1", "true", "yes"}
CONTINUAL_TRAINING_INTERVAL_SECONDS = int(
    os.getenv(
        "CONTINUAL_TRAINING_INTERVAL_SECONDS",
        str(int(float(os.getenv("SCRAPING_INTERVAL_HOURS", "1")) * 3600)),
    )
)

http_client: httpx.AsyncClient | None = None
trainer_task: asyncio.Task | None = None
training_state: dict[str, Any] = {
    "enabled": CONTINUAL_TRAINING_ENABLED,
    "cycles": 0,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
    "last_summary": None,
}
TELEMETRY_WINDOW_SIZE = max(1, int(os.getenv("PIPELINE_TELEMETRY_WINDOW", "200")))
TELEMETRY_STAGE_NAMES = ("scrape", "sbert", "ncf", "dqn", "calibrator", "aggregation")
TELEMETRY_STAGE_ALIASES = {
    "scrape": "scrape",
    "encode": "sbert",
    "ncf_score": "ncf",
    "dqn_rank": "dqn",
    "calibrator": "calibrator",
    "aggregate": "aggregation",
}
STAGE_LATENCY_HISTORY: dict[str, deque[float]] = {
    stage: deque(maxlen=TELEMETRY_WINDOW_SIZE) for stage in TELEMETRY_STAGE_NAMES
}

# NOTE: removed in-process USER_PROFILE_CACHE. The gateway always sends the
# full profile in the request payload, so a cache added no value while creating
# an unbounded memory leak and a stale-data foot-gun.


class PipelineRunRequest(BaseModel):
    user_id: int | str
    refresh_jobs: bool = False
    profile: dict[str, Any] | None = None
    interaction_count: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PipelineRunResponse(BaseModel):
    run_id: str
    user_id: str
    refresh_jobs: bool
    total_candidates: int
    ranked: list[dict[str, Any]]
    timings_ms: dict[str, float]
    stages: dict[str, Any]


class FeedbackRequest(BaseModel):
    user_id: int | str
    job_id: str
    event: str = "view"
    reward: float | None = None
    profile: dict[str, Any] | None = None
    job: dict[str, Any] | None = None
    interaction_count: int = Field(default=0, ge=0)
    run_id: str | None = None
    served_slate_id: str | None = None
    rank: int | None = Field(default=None, ge=1)


def require_internal_service_token(
    x_internal_service_token: str | None = Header(default=None, alias=INTERNAL_SERVICE_TOKEN_HEADER),
) -> None:
    if not INTERNAL_SERVICE_TOKEN:
        return
    if not hmac.compare_digest(x_internal_service_token or "", INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="internal service token required")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global http_client, trainer_task
    timeout = httpx.Timeout(HTTP_TIMEOUT_SECONDS, connect=1.0)
    http_client = httpx.AsyncClient(timeout=timeout)
    logger.info(
        "Pipeline started scraper=%s sbert=%s ncf=%s dqn=%s p95_target_ms=%s",
        SCRAPER_URL,
        SBERT_URL,
        NCF_URL,
        DQN_URL,
        P95_TARGET_MS,
    )
    if CONTINUAL_TRAINING_ENABLED:
        trainer_task = asyncio.create_task(_continual_training_loop())
    try:
        yield
    finally:
        if trainer_task is not None:
            trainer_task.cancel()
            try:
                await trainer_task
            except asyncio.CancelledError:
                pass
        await http_client.aclose()


api = FastAPI(
    title="SCPA Pipeline Orchestrator",
    version="3.0.0",
    description="Orchestrates Scrape -> Encode -> NCF -> DQN -> Aggregate via HTTP.",
    lifespan=lifespan,
)
app = api
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _stage(name: str, timings: dict[str, float], awaitable):
    started = time.perf_counter()
    result = await awaitable
    timings[name] = round((time.perf_counter() - started) * 1000, 2)
    _record_stage_latency(name, timings[name])
    summary = getattr(result, "summary", None)
    logger.info("stage=%s duration_ms=%.2f summary=%s", name, timings[name], summary)
    return result


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(ordered[int(rank)], 2)
    weight = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * weight, 2)


def _record_stage_latency(stage_name: str, duration_ms: float) -> None:
    canonical = TELEMETRY_STAGE_ALIASES.get(stage_name, stage_name)
    history = STAGE_LATENCY_HISTORY.setdefault(
        canonical,
        deque(maxlen=TELEMETRY_WINDOW_SIZE),
    )
    history.append(round(max(0.0, float(duration_ms)), 2))


def _stage_latency_stats(stage_name: str) -> dict[str, float | int]:
    values = list(STAGE_LATENCY_HISTORY.get(stage_name, ()))
    return {
        "count": len(values),
        "last_ms": round(values[-1], 2) if values else 0.0,
        "p50_ms": _percentile(values, 50.0),
        "p95_ms": _percentile(values, 95.0),
    }


def _telemetry_snapshot() -> dict[str, Any]:
    return {
        "window_size": TELEMETRY_WINDOW_SIZE,
        "p95_target_ms": P95_TARGET_MS,
        "stages": {
            stage: _stage_latency_stats(stage)
            for stage in TELEMETRY_STAGE_NAMES
        },
    }


async def _run_scrape_embedding_cycle(refresh_jobs: bool = True) -> dict[str, Any]:
    if http_client is None:
        raise RuntimeError("pipeline HTTP client not ready")
    scrape = await run_scrape_stage(
        client=http_client,
        scraper_url=SCRAPER_URL,
        user_id="trainer",
        profile={"program_studi": "mixed", "jurusan": "mixed", "skills": []},
        interaction_count=0,
        refresh_jobs=refresh_jobs,
        limit=SCRAPE_TARGET,
    )
    encoded = await run_encode_stage(http_client, SBERT_URL, scrape.user, scrape.jobs)
    JOB_CACHE[:] = encoded.jobs
    ncf_payload = {
        "jobs": [
            {
                "id": str(job["id"]),
                "title": job.get("title") or "",
                "description": job.get("description") or "",
                "tags": job.get("tags") or [],
                "embedding": job.get("embedding") or [],
                "sbert_score": float(job.get("sbert_score") or 0.0),
            }
            for job in encoded.jobs
        ]
    }
    dqn_payload = {"jobs": encoded.jobs}
    ncf_response = await http_client.post(f"{NCF_URL}/jobs/upsert", json=ncf_payload)
    ncf_response.raise_for_status()
    dqn_response = await http_client.post(f"{DQN_URL}/jobs/upsert", json=dqn_payload)
    dqn_response.raise_for_status()
    return {
        "jobs": len(encoded.jobs),
        "ncf": ncf_response.json(),
        "dqn": dqn_response.json(),
    }


async def _continual_training_loop() -> None:
    while True:
        try:
            training_state["last_started_at"] = time.time()
            summary = await _run_scrape_embedding_cycle(refresh_jobs=True)
            training_state["cycles"] += 1
            training_state["last_summary"] = summary
            training_state["last_error"] = None
            training_state["last_finished_at"] = time.time()
            logger.info("continual_training cycle=%s summary=%s", training_state["cycles"], summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            training_state["last_error"] = str(exc)
            training_state["last_finished_at"] = time.time()
            logger.exception("continual_training failed")
        await asyncio.sleep(CONTINUAL_TRAINING_INTERVAL_SECONDS)


@api.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "pipeline",
        "mode": "http-orchestration-only",
        "p95_target_ms": P95_TARGET_MS,
        "downstream": {
            "scraper": SCRAPER_URL,
            "sbert": SBERT_URL,
            "ncf": NCF_URL,
            "dqn": DQN_URL,
        },
        "continual_training": {
            "enabled": CONTINUAL_TRAINING_ENABLED,
            "interval_seconds": CONTINUAL_TRAINING_INTERVAL_SECONDS,
            "cycles": training_state["cycles"],
            "last_error": training_state["last_error"],
            "scrape_target": SCRAPE_TARGET,
            "candidate_pool_limit": CANDIDATE_POOL_LIMIT,
        },
        "telemetry": _telemetry_snapshot(),
    }


@api.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    dependencies=[Depends(require_internal_service_token)],
)
async def run_pipeline(request: PipelineRunRequest) -> PipelineRunResponse:
    if http_client is None:
        raise HTTPException(status_code=503, detail="pipeline not ready")

    run_id = f"pipe-{uuid.uuid4().hex}"
    timings: dict[str, float] = {}
    stages: dict[str, Any] = {"run": {"run_id": run_id}}
    started = time.perf_counter()
    output_limit = min(int(request.limit or DEFAULT_JOB_LIMIT), 100)
    candidate_limit = max(output_limit, CANDIDATE_POOL_LIMIT)

    scrape = await _stage(
        "scrape",
        timings,
        run_scrape_stage(
            client=http_client,
            scraper_url=SCRAPER_URL,
            user_id=str(request.user_id),
            profile=request.profile,
            interaction_count=request.interaction_count,
            refresh_jobs=request.refresh_jobs,
            limit=candidate_limit,
        ),
    )
    stages["scrape"] = scrape.summary

    if not scrape.jobs:
        timings["total"] = round((time.perf_counter() - started) * 1000, 2)
        stages["degradation"] = {
            "degraded": True,
            "reason": "empty_candidates",
            "fallback_flags": ["empty_candidates"],
        }
        stages["telemetry"] = _telemetry_snapshot()
        return PipelineRunResponse(
            run_id=run_id,
            user_id=str(request.user_id),
            refresh_jobs=request.refresh_jobs,
            total_candidates=0,
            ranked=[],
            timings_ms=timings,
            stages=stages,
        )

    encoded = await _stage("encode", timings, run_encode_stage(http_client, SBERT_URL, scrape.user, scrape.jobs))
    stages["encode"] = encoded.summary
    JOB_CACHE[:] = encoded.jobs

    ncf_scored = await _stage(
        "ncf_score",
        timings,
        run_ncf_score_stage(http_client, NCF_URL, scrape.user, encoded.jobs),
    )
    stages["ncf_score"] = ncf_scored.summary

    dqn_ranked = await _stage(
        "dqn_rank",
        timings,
        run_dqn_rank_stage(http_client, DQN_URL, scrape.user, ncf_scored.jobs),
    )
    stages["dqn_rank"] = dqn_ranked.summary

    timings["calibrator"] = 0.0
    _record_stage_latency("calibrator", timings["calibrator"])
    stages["calibrator"] = {
        "mode": "pending_aggregate_calibrator",
        "duration_ms": timings["calibrator"],
    }

    aggregated = await _stage("aggregate", timings, run_aggregate_stage(scrape.user, dqn_ranked.jobs))
    stages["aggregate"] = aggregated.summary
    if isinstance(aggregated.summary.get("calibrator"), dict):
        stages["calibrator"] = {
            **aggregated.summary["calibrator"],
            "duration_ms": timings["calibrator"],
        }
    timings["total"] = round((time.perf_counter() - started) * 1000, 2)
    stages["telemetry"] = _telemetry_snapshot()
    fallback_flags: list[str] = []
    if "fallback" in str(stages.get("scrape", {}).get("source", "")).lower():
        fallback_flags.append("scraper_fallback")
    fallback_flags.extend(stages.get("encode", {}).get("fallback_flags", []))
    model_provenance = {
        "pipeline_run_id": run_id,
        "sbert": {
            "model_name": stages.get("encode", {}).get("model_name"),
            "model_version": stages.get("encode", {}).get("model_version"),
            "embedding_dim": stages.get("encode", {}).get("embedding_dim"),
        },
        "ncf": {"model_version": stages.get("ncf_score", {}).get("model_version")},
        "dqn": {
            "model_version": stages.get("dqn_rank", {}).get("model_version"),
            "policy_sources": stages.get("dqn_rank", {}).get("policy_sources", []),
        },
        "weights": stages.get("aggregate", {}).get("weights", {}),
    }
    ranked = [
        {
            **job,
            "rank": index,
            "run_id": run_id,
            "pipeline_run_id": run_id,
            "served_slate_id": run_id,
            "model_provenance": model_provenance,
            "fallback_flags": fallback_flags,
        }
        for index, job in enumerate(aggregated.ranked[:output_limit], start=1)
    ]

    return PipelineRunResponse(
        run_id=run_id,
        user_id=str(request.user_id),
        refresh_jobs=request.refresh_jobs,
        total_candidates=len(scrape.jobs),
        ranked=ranked,
        timings_ms=timings,
        stages=stages,
    )


@api.get("/training/status", dependencies=[Depends(require_internal_service_token)])
async def training_status() -> dict[str, Any]:
    return training_state


@api.post("/training/run-once", dependencies=[Depends(require_internal_service_token)])
async def training_run_once() -> dict[str, Any]:
    summary = await _run_scrape_embedding_cycle(refresh_jobs=True)
    training_state["cycles"] += 1
    training_state["last_summary"] = summary
    training_state["last_error"] = None
    training_state["last_finished_at"] = time.time()
    return {"status": "ok", **summary}


@api.post("/feedback", dependencies=[Depends(require_internal_service_token)])
async def feedback(request: FeedbackRequest) -> dict[str, Any]:
    if http_client is None:
        raise HTTPException(status_code=503, detail="pipeline not ready")
    profile = request.profile or {}
    skills = profile.get("skills") or []
    profile_text = f"{profile.get('program_studi') or profile.get('jurusan') or ''} {profile.get('jurusan') or ''} {' '.join(map(str, skills))}"
    texts = [profile_text]
    if request.job:
        texts.append(" ".join(str(request.job.get(key) or "") for key in ("title", "description", "tags")))
    embed_response = await http_client.post(f"{SBERT_URL}/encode", json={"texts": texts})
    embed_response.raise_for_status()
    embeddings = embed_response.json().get("embeddings", [])
    user_embedding = embeddings[0] if embeddings else []
    job_embedding = embeddings[1] if len(embeddings) > 1 else (request.job or {}).get("embedding")
    ncf_response = await http_client.post(
        f"{NCF_URL}/feedback",
        json={
            "user_id": str(request.user_id),
            "job_id": request.job_id,
            "event": request.event,
            "value": request.reward,
            "profile_text": profile_text,
            "user_embedding": user_embedding,
            "job_embedding": job_embedding,
        },
    )
    ncf_response.raise_for_status()
    dqn_response = await http_client.post(
        f"{DQN_URL}/reward",
        json={
            "user_id": str(request.user_id),
            "job_id": request.job_id,
            "event": request.event,
            "reward": request.reward,
            "job": {**(request.job or {"id": request.job_id}), "embedding": job_embedding or []},
            "state": {
                "interaction_count": request.interaction_count,
                "pipeline_run_id": request.run_id,
                "served_slate_id": request.served_slate_id,
                "rank": request.rank,
            },
            "done": False,
        },
    )
    dqn_response.raise_for_status()
    return {
        "status": "trained",
        "slate_context": {
            "pipeline_run_id": request.run_id,
            "served_slate_id": request.served_slate_id,
            "rank": request.rank,
        },
        "ncf": ncf_response.json(),
        "dqn": dqn_response.json(),
    }


@api.post(
    "/pipeline/invalidate-user/{user_id}",
    dependencies=[Depends(require_internal_service_token)],
)
async def invalidate_user(user_id: str) -> dict[str, Any]:
    """Forward cache-bust to NCF so the next recommendation rebuilds the user vector.

    Safe to call when NCF is down; errors are swallowed so a transient outage
    does not block profile saves.
    """
    uid = str(user_id)
    ncf_status: dict[str, Any] = {"status": "skipped"}
    if http_client is not None:
        try:
            response = await http_client.post(
                f"{NCF_URL}/users/{uid}/invalidate",
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            ncf_status = response.json()
        except httpx.HTTPError as exc:
            logger.warning("ncf invalidation failed user_id=%s: %s", uid, exc)
            ncf_status = {"status": "error", "error": str(exc)}
    return {
        "status": "ok",
        "user_id": uid,
        "ncf": ncf_status,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:api", host="0.0.0.0", port=int(os.getenv("SERVICE_PORT", "8005")))
