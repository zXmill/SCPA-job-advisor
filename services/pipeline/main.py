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

from sqlalchemy import text as sa_text

from services.shared.contracts import (
    DQN_MODE_DISABLED_COLD_START,
    SEGMENT_COLD_START,
    SOURCE_EMPTY_CANDIDATES,
    SOURCE_HYBRID_MODEL,
    SOURCE_SEMANTIC_COLD_START,
)
from services.shared.model_bundle import (
    ACTIVE_BUNDLE_SQL,
    ModelBundle,
    bundle_from_row,
)

try:
    from .stages.stage_1_scrape import (
        JOB_CACHE,
        _build_user,
        _load_db_jobs,
        persist_job_embeddings,
        run_scrape_stage,
        _get_db_engine,
    )
    from .stages.stage_2_encode import run_encode_stage
    from .stages.stage_3_ncf_score import run_ncf_score_stage
    from .stages.stage_4_dqn_rank import _pre_dqn_score, run_dqn_rank_stage
    from .stages.stage_5_aggregate import run_aggregate_stage
    from .stages.stage_retrieval import RetrievalError, run_retrieval_stage
except ImportError:  # pragma: no cover - used when running from services/pipeline
    from stages.stage_1_scrape import (  # type: ignore[no-redef]
        JOB_CACHE,
        _build_user,
        _load_db_jobs,
        persist_job_embeddings,
        run_scrape_stage,
        _get_db_engine,
    )
    from stages.stage_2_encode import run_encode_stage
    from stages.stage_3_ncf_score import run_ncf_score_stage
    from stages.stage_4_dqn_rank import _pre_dqn_score, run_dqn_rank_stage
    from stages.stage_5_aggregate import run_aggregate_stage
    from stages.stage_retrieval import RetrievalError, run_retrieval_stage


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
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "65"))
DEFAULT_JOB_LIMIT = int(os.getenv("PIPELINE_JOB_LIMIT", "20"))
CANDIDATE_POOL_LIMIT = int(os.getenv("PIPELINE_CANDIDATE_POOL_LIMIT", "250"))
SCRAPE_REFRESH_LIMIT = max(1, int(os.getenv("PIPELINE_SCRAPE_REFRESH_LIMIT", "10")))
# Hard ceiling for a manual "Scrape Now" cycle; on timeout the job fails instead
# of hanging in the running state forever. Generous by default because a full
# refresh fetches many external seeds (I/O-bound, legitimately minutes long).
MANUAL_SCRAPE_TIMEOUT_SECONDS = max(30, int(os.getenv("MANUAL_SCRAPE_TIMEOUT_SECONDS", "1800")))
SCRAPE_TARGET = int(os.getenv("JOBS_TARGET", "2000"))
P95_TARGET_MS = int(os.getenv("PIPELINE_P95_TARGET_MS", "150"))
# Online retrieval mode: 'pgvector' (target architecture) or 'legacy'
# (rollback flag; restores bulk DB candidates + request-time encode).
PIPELINE_RETRIEVAL_MODE = os.getenv("PIPELINE_RETRIEVAL_MODE", "pgvector").strip().lower()
RETRIEVAL_TOP_K = max(10, int(os.getenv("PIPELINE_RETRIEVAL_TOP_K", "100")))
NCF_OUTPUT_TOP_K = max(5, int(os.getenv("PIPELINE_NCF_OUTPUT_TOP_K", "50")))
DQN_OUTPUT_TOP_K = max(5, int(os.getenv("PIPELINE_DQN_OUTPUT_TOP_K", "20")))
MIN_EMBEDDING_COVERAGE = float(os.getenv("PIPELINE_MIN_EMBEDDING_COVERAGE", "0.95"))
MAX_PENDING_TASK_AGE_SECONDS = float(os.getenv("PIPELINE_MAX_PENDING_AGE", "86400"))
USER_ENCODE_TIMEOUT_SECONDS = float(os.getenv("PIPELINE_USER_ENCODE_TIMEOUT", "2.0"))
BUNDLE_CACHE_TTL_SECONDS = float(os.getenv("PIPELINE_BUNDLE_TTL", "60"))
CONTINUAL_TRAINING_ENABLED = os.getenv("CONTINUAL_TRAINING_ENABLED", "true").lower() in {"1", "true", "yes"}
CONTINUAL_TRAINING_INTERVAL_SECONDS = int(
    os.getenv(
        "CONTINUAL_TRAINING_INTERVAL_SECONDS",
        str(int(float(os.getenv("SCRAPING_INTERVAL_HOURS", "1")) * 3600)),
    )
)

http_client: httpx.AsyncClient | None = None
trainer_task: asyncio.Task | None = None
warmup_task: asyncio.Task | None = None
EMBEDDING_WARMUP_ENABLED = os.getenv("EMBEDDING_WARMUP_ENABLED", "true").lower() in {"1", "true", "yes"}
EMBEDDING_WARMUP_CHUNK = max(1, int(os.getenv("EMBEDDING_WARMUP_CHUNK", "64")))
warmup_state: dict[str, Any] = {
    "enabled": EMBEDDING_WARMUP_ENABLED,
    "status": "pending",
    "embedded_jobs": 0,
    "persisted_jobs": 0,
    "total_jobs": 0,
    "last_error": None,
    "finished_at": None,
}
training_state: dict[str, Any] = {
    "enabled": CONTINUAL_TRAINING_ENABLED,
    "cycles": 0,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
    "last_summary": None,
}
# Manual on-demand scrape ("Scrape Now") job state. Single-flight: only one
# manual cycle runs at a time. Status: idle | running | completed | failed.
scrape_run_state: dict[str, Any] = {
    "job_id": None,
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "summary": None,
    "error": None,
    "triggered_by": None,
    "seed_offset": 0,
    # Rotating cursor so repeated manual scrapes walk the full seed list
    # (incl. tail queries like engineering) instead of re-scraping offset 0.
    "next_seed_offset": 0,
}
# How far the manual seed cursor advances per click, and the wrap modulus.
# Stride defaults to the per-cycle scrape limit so clicks tile the seed list.
MANUAL_SCRAPE_SEED_STRIDE = max(1, int(os.getenv("PIPELINE_MANUAL_SCRAPE_STRIDE", "10")))
MANUAL_SCRAPE_SEED_MODULUS = max(1, int(os.getenv("PIPELINE_MANUAL_SCRAPE_SEED_MODULUS", "400")))
TELEMETRY_WINDOW_SIZE = max(1, int(os.getenv("PIPELINE_TELEMETRY_WINDOW", "200")))
TELEMETRY_STAGE_NAMES = ("scrape", "sbert", "ncf", "dqn", "calibrator", "aggregation")
TELEMETRY_STAGE_ALIASES = {
    "scrape": "scrape",
    "encode": "sbert",
    "retrieval": "sbert",
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
    limit: int = Field(default=20, ge=1, le=1000)


class PipelineRunResponse(BaseModel):
    run_id: str
    user_id: str
    refresh_jobs: bool
    total_candidates: int
    ranked: list[dict[str, Any]]
    timings_ms: dict[str, float]
    stages: dict[str, Any]
    source: str | None = None
    model_bundle_version: str | None = None


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
    rank: int | None = Field(default=None, ge=0)


def require_internal_service_token(
    x_internal_service_token: str | None = Header(default=None, alias=INTERNAL_SERVICE_TOKEN_HEADER),
) -> None:
    if not INTERNAL_SERVICE_TOKEN:
        return
    if not hmac.compare_digest(x_internal_service_token or "", INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="internal service token required")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global http_client, trainer_task, warmup_task
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
    # Startup warmup is a legacy-mode construct only: in pgvector mode the
    # embedding worker owns coverage and a service restart must never trigger
    # catalog-wide encoding (contract §13).
    if EMBEDDING_WARMUP_ENABLED and PIPELINE_RETRIEVAL_MODE == "legacy":
        warmup_task = asyncio.create_task(_embedding_warmup())
    else:
        warmup_state["status"] = "disabled"
    if CONTINUAL_TRAINING_ENABLED:
        trainer_task = asyncio.create_task(_continual_training_loop())
    try:
        yield
    finally:
        for task in (trainer_task, warmup_task):
            if task is not None:
                task.cancel()
                try:
                    await task
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
    try:
        result = await awaitable
    except httpx.TimeoutException as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.error("stage=%s failed duration_ms=%.2f error=timeout detail=%s", name, duration_ms, exc)
        raise HTTPException(
            status_code=504,
            detail={"stage": name, "error": "downstream_timeout", "message": str(exc) or "timed out"},
        ) from exc
    except httpx.HTTPStatusError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.error(
            "stage=%s failed duration_ms=%.2f error=http_%s body=%s",
            name, duration_ms, exc.response.status_code, exc.response.text[:300],
        )
        raise HTTPException(
            status_code=502,
            detail={
                "stage": name,
                "error": "downstream_http_error",
                "downstream_status": exc.response.status_code,
                "message": f"Downstream service returned HTTP {exc.response.status_code}",
            },
        ) from exc
    except httpx.HTTPError as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.error("stage=%s failed duration_ms=%.2f error=transport detail=%s", name, duration_ms, exc)
        raise HTTPException(
            status_code=502,
            detail={"stage": name, "error": "downstream_unavailable", "message": str(exc) or "transport error"},
        ) from exc
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


async def _run_scrape_embedding_cycle(refresh_jobs: bool = True, seed_offset: int = 0) -> dict[str, Any]:
    if http_client is None:
        raise RuntimeError("pipeline HTTP client not ready")
    scrape = await run_scrape_stage(
        client=http_client,
        scraper_url=SCRAPER_URL,
        user_id="trainer",
        profile={"program_studi": "mixed", "jurusan": "mixed", "skills": []},
        interaction_count=0,
        refresh_jobs=refresh_jobs,
        limit=min(SCRAPE_TARGET, SCRAPE_REFRESH_LIMIT),
        seed_offset=max(0, int(seed_offset or 0)),
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


async def _embedding_warmup() -> None:
    """Embed and persist all active DB jobs missing a cached SBERT embedding."""
    warmup_state["status"] = "running"
    from sqlalchemy import text
    try:
        engine = _get_db_engine()
        if engine is None:
            raise RuntimeError("Database not available for warmup")
        if http_client is None:
            raise RuntimeError("pipeline HTTP client not ready")
            
        async with engine.connect() as conn:
            lock_acquired = await conn.execute(text("SELECT pg_try_advisory_lock(1001)"))
            if not lock_acquired.scalar():
                logger.info("embedding_warmup skipped: another replica holds the lock")
                warmup_state["status"] = "completed"
                return
            
            try:
                limit = 250
                offset = 0
                embedded_total = 0
                persisted_total = 0
                warm_user = {"profile_text": "warmup"}
                
                while True:
                    jobs = await _load_db_jobs(limit, offset)
                    if not jobs:
                        break
                    warmup_state["total_jobs"] = offset + len(jobs)
                    
                    for start in range(0, len(jobs), EMBEDDING_WARMUP_CHUNK):
                        chunk = jobs[start:start + EMBEDDING_WARMUP_CHUNK]
                        encoded = await run_encode_stage(
                            http_client,
                            SBERT_URL,
                            dict(warm_user),
                            chunk,
                            max_uncached=EMBEDDING_WARMUP_CHUNK,
                        )
                        fresh = [
                            job for job in encoded.jobs
                            if job.get("embedding") and job.get("embedding_text_hash")
                        ]
                        embedded_total += int(encoded.summary.get("job_embedding_cache_misses") or 0)
                        persisted_total += await persist_job_embeddings(fresh)
                        warmup_state["embedded_jobs"] = embedded_total
                        warmup_state["persisted_jobs"] = persisted_total
                        # Yield to interactive traffic and prevent monopolization
                        await asyncio.sleep(0.5)
                        
                    offset += limit
            finally:
                await conn.execute(text("SELECT pg_advisory_unlock(1001)"))
                
        warmup_state["status"] = "completed"
        warmup_state["last_error"] = None
        logger.info(
            "embedding_warmup completed total_jobs=%s embedded=%s persisted=%s",
            warmup_state["total_jobs"], embedded_total, persisted_total,
        )
    except asyncio.CancelledError:
        warmup_state["status"] = "cancelled"
        raise
    except Exception as exc:  # pylint: disable=broad-except
        warmup_state["status"] = "failed"
        warmup_state["last_error"] = str(exc)
        logger.exception("embedding_warmup failed")
    finally:
        warmup_state["finished_at"] = time.time()


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


_bundle_cache: dict[str, Any] = {"bundle": None, "loaded_at": 0.0}


async def _get_active_bundle() -> ModelBundle:
    """Active bundle from model_bundles with a short TTL cache; falls back to
    schema defaults so the pipeline can still serve when the DB row is gone."""
    now = time.time()
    cached = _bundle_cache["bundle"]
    if cached is not None and now - _bundle_cache["loaded_at"] < BUNDLE_CACHE_TTL_SECONDS:
        return cached
    bundle = ModelBundle()
    engine = _get_db_engine()
    if engine is not None:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(sa_text(ACTIVE_BUNDLE_SQL))
                row = result.mappings().first()
            bundle = bundle_from_row(dict(row) if row is not None else None)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("active bundle load failed, using defaults: %s", exc)
    _bundle_cache["bundle"] = bundle
    _bundle_cache["loaded_at"] = now
    return bundle


def _filter_lineage(
    jobs: list[dict[str, Any]],
    allowed_ids: set[str],
    stage_name: str,
) -> list[dict[str, Any]]:
    """Enforce the candidate lineage invariant: downstream rerankers must not
    introduce job IDs. Violations are dropped and logged, never served."""
    kept = [job for job in jobs if str(job.get("id")) in allowed_ids]
    dropped = len(jobs) - len(kept)
    if dropped:
        logger.error(
            "funnel_lineage_violation stage=%s dropped=%s", stage_name, dropped
        )
    return kept


async def _run_pipeline_pgvector(request: PipelineRunRequest) -> PipelineRunResponse:
    bundle = await _get_active_bundle()
    run_id = f"pipe-{uuid.uuid4().hex}"
    timings: dict[str, float] = {}
    stages: dict[str, Any] = {"run": {"run_id": run_id, "retrieval_mode": "pgvector"}}
    started = time.perf_counter()
    output_limit = min(int(request.limit or DEFAULT_JOB_LIMIT), DQN_OUTPUT_TOP_K)
    user = _build_user(str(request.user_id), request.profile, request.interaction_count)

    try:
        retrieval = await _stage(
            "retrieval",
            timings,
            run_retrieval_stage(
                http_client,
                SBERT_URL,
                user,
                model_version=bundle.sbert_model_version,
                top_k=RETRIEVAL_TOP_K,
                encode_timeout=USER_ENCODE_TIMEOUT_SECONDS,
            ),
        )
    except RetrievalError as exc:
        raise HTTPException(
            status_code=503,
            detail={"stage": "retrieval", "error": exc.code, "message": str(exc)},
        ) from exc
    stages["retrieval"] = retrieval.summary
    candidates = retrieval.jobs

    def _final(ranked: list[dict[str, Any]], source: str, degraded: bool = False) -> PipelineRunResponse:
        timings["total"] = round((time.perf_counter() - started) * 1000, 2)
        stages["telemetry"] = _telemetry_snapshot()
        if degraded:
            stages["degradation"] = {
                "degraded": True,
                "reason": source,
                "fallback_flags": [source],
            }
        return PipelineRunResponse(
            run_id=run_id,
            user_id=str(request.user_id),
            refresh_jobs=request.refresh_jobs,
            total_candidates=len(candidates),
            ranked=ranked,
            timings_ms=timings,
            stages=stages,
            source=source,
            model_bundle_version=bundle.bundle_version,
        )

    if not candidates:
        # Controlled empty slate: DQN/NCF are never called with zero candidates.
        return _final([], SOURCE_EMPTY_CANDIDATES, degraded=True)

    retrieval_ids = {str(job.get("id")) for job in candidates}

    ncf_scored = await _stage(
        "ncf_score",
        timings,
        run_ncf_score_stage(http_client, NCF_URL, user, candidates),
    )
    stages["ncf_score"] = ncf_scored.summary
    ncf_jobs = _filter_lineage(ncf_scored.jobs, retrieval_ids, "ncf_score")
    ncf_top = sorted(ncf_jobs, key=_pre_dqn_score, reverse=True)[:NCF_OUTPUT_TOP_K]
    stages["ncf_score"]["funnel"] = {
        "input": len(candidates),
        "output": len(ncf_top),
        "cap": NCF_OUTPUT_TOP_K,
    }

    dqn_ranked = await _stage(
        "dqn_rank",
        timings,
        run_dqn_rank_stage(http_client, DQN_URL, user, ncf_top),
    )
    stages["dqn_rank"] = dqn_ranked.summary
    ncf_top_ids = {str(job.get("id")) for job in ncf_top}
    dqn_jobs = _filter_lineage(dqn_ranked.jobs, ncf_top_ids, "dqn_rank")[:DQN_OUTPUT_TOP_K]
    stages["dqn_rank"]["funnel"] = {
        "input": len(ncf_top),
        "output": len(dqn_jobs),
        "cap": DQN_OUTPUT_TOP_K,
    }

    timings["calibrator"] = 0.0
    _record_stage_latency("calibrator", timings["calibrator"])
    aggregated = await _stage(
        "aggregate", timings, run_aggregate_stage(user, dqn_jobs, bundle=bundle)
    )
    stages["aggregate"] = aggregated.summary
    if isinstance(aggregated.summary.get("calibrator"), dict):
        stages["calibrator"] = {
            **aggregated.summary["calibrator"],
            "duration_ms": timings["calibrator"],
        }

    segment = str(aggregated.summary.get("segment") or "")
    dqn_mode = str(stages["dqn_rank"].get("dqn_mode") or "")
    if segment == SEGMENT_COLD_START or dqn_mode == DQN_MODE_DISABLED_COLD_START:
        source = SOURCE_SEMANTIC_COLD_START
    else:
        source = SOURCE_HYBRID_MODEL

    model_provenance = {
        "pipeline_run_id": run_id,
        "model_bundle_version": bundle.bundle_version,
        "sbert": {
            "model_version": stages["retrieval"].get("model_version"),
            "embedding_dim": stages["retrieval"].get("embedding_dim"),
            "checkpoint_hash": stages["retrieval"].get("checkpoint_hash"),
            "candidate_pool_source": "pgvector_top_k",
        },
        "ncf": {"model_version": stages["ncf_score"].get("model_version")},
        "dqn": {
            "model_version": stages["dqn_rank"].get("model_version"),
            "policy_objective": stages["dqn_rank"].get("policy_objective"),
            "policy_sources": stages["dqn_rank"].get("policy_sources", []),
            "rerank_reasons": stages["dqn_rank"].get("rerank_reasons", []),
        },
        "weights": stages["aggregate"].get("weights", {}),
    }
    ranked = [
        {
            **job,
            "rank": index,
            "run_id": run_id,
            "pipeline_run_id": run_id,
            "served_slate_id": run_id,
            "model_provenance": model_provenance,
            "fallback_flags": [],
        }
        for index, job in enumerate(aggregated.ranked[:output_limit], start=1)
    ]
    return _final(ranked, source)


@api.get("/health")
async def health() -> dict[str, Any]:
    if PIPELINE_RETRIEVAL_MODE == "pgvector":
        is_ready = True  # liveness only; dependency-aware checks live in /readiness
    else:
        is_ready = not EMBEDDING_WARMUP_ENABLED or warmup_state["status"] == "completed"
    return {
        "status": "healthy",
        "is_ready": is_ready,
        "retrieval_mode": PIPELINE_RETRIEVAL_MODE,
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
        "embedding_warmup": dict(warmup_state),
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

    if PIPELINE_RETRIEVAL_MODE == "pgvector":
        return await _run_pipeline_pgvector(request)

    if EMBEDDING_WARMUP_ENABLED and warmup_state["status"] != "completed":
        raise HTTPException(status_code=503, detail={"stage": "pipeline", "error": "warming_up", "message": "Pipeline candidate cache is still warming up"})

    run_id = f"pipe-{uuid.uuid4().hex}"
    timings: dict[str, float] = {}
    stages: dict[str, Any] = {"run": {"run_id": run_id}}
    started = time.perf_counter()
    output_limit = min(int(request.limit or DEFAULT_JOB_LIMIT), 100)
    candidate_limit = max(output_limit, CANDIDATE_POOL_LIMIT)
    scrape_limit = min(candidate_limit, SCRAPE_REFRESH_LIMIT)

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
            limit=scrape_limit,
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
    if int(encoded.summary.get("job_embedding_cache_misses") or 0) > 0:
        persisted = await persist_job_embeddings(encoded.jobs)
        stages["encode"]["persisted_job_embeddings"] = persisted

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
            "policy_objective": stages.get("dqn_rank", {}).get("policy_objective"),
            "policy_sources": stages.get("dqn_rank", {}).get("policy_sources", []),
            "rerank_reasons": stages.get("dqn_rank", {}).get("rerank_reasons", []),
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


_READINESS_COVERAGE_SQL = sa_text(
    """
    SELECT
      (SELECT count(*) FROM jobs WHERE is_active AND quality_status = 'accepted') AS active_jobs,
      (SELECT count(*) FROM jobs j WHERE j.is_active AND j.quality_status = 'accepted'
         AND EXISTS (SELECT 1 FROM job_embeddings je WHERE je.job_id = j.id
                     AND je.model_version = :model AND je.status = 'ready')) AS covered,
      (SELECT EXTRACT(EPOCH FROM (NOW() - min(created_at)))
         FROM embedding_tasks WHERE status IN ('pending','retry')) AS oldest_pending_seconds
    """
)


@api.get("/readiness")
async def readiness() -> Any:
    """Dependency-aware readiness (contract §9/§13). Liveness stays /health."""
    from fastapi.responses import JSONResponse

    checks: dict[str, Any] = {"retrieval_mode": PIPELINE_RETRIEVAL_MODE}
    ready = True

    bundle = await _get_active_bundle()
    checks["bundle"] = {
        "bundle_version": bundle.bundle_version,
        "sbert_model_version": bundle.sbert_model_version,
        "source": bundle.source,
    }

    engine = _get_db_engine()
    if engine is None:
        checks["database"] = "unavailable"
        ready = False
    else:
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    _READINESS_COVERAGE_SQL, {"model": bundle.sbert_model_version}
                )
                row = result.mappings().first() or {}
            active_jobs = int(row.get("active_jobs") or 0)
            covered = int(row.get("covered") or 0)
            oldest = row.get("oldest_pending_seconds")
            coverage = (covered / active_jobs) if active_jobs else 0.0
            checks["database"] = "ok"
            checks["embedding_coverage"] = {
                "active_jobs": active_jobs,
                "covered": covered,
                "coverage": round(coverage, 4),
                "threshold": MIN_EMBEDDING_COVERAGE,
            }
            checks["oldest_pending_task_seconds"] = (
                round(float(oldest), 1) if oldest is not None else None
            )
            if PIPELINE_RETRIEVAL_MODE == "pgvector":
                if coverage < MIN_EMBEDDING_COVERAGE:
                    ready = False
                if oldest is not None and float(oldest) > MAX_PENDING_TASK_AGE_SECONDS:
                    ready = False
        except Exception as exc:  # pylint: disable=broad-except
            checks["database"] = f"error: {type(exc).__name__}"
            ready = False

    if http_client is not None:
        try:
            response = await http_client.get(f"{SBERT_URL}/ready", timeout=3)
            sbert_payload = response.json()
            checks["sbert"] = {
                "ready": response.status_code == 200,
                "model_version": sbert_payload.get("model_version"),
                "checkpoint_hash": sbert_payload.get("checkpoint_hash"),
                "embedding_dim": sbert_payload.get("embedding_dim"),
            }
            if response.status_code != 200:
                ready = False
            elif str(sbert_payload.get("model_version")) != bundle.sbert_model_version:
                checks["sbert"]["bundle_mismatch"] = True
                ready = False
        except httpx.HTTPError as exc:
            checks["sbert"] = {"ready": False, "error": str(exc)[:120]}
            ready = False
    else:
        checks["sbert"] = {"ready": False, "error": "http client not started"}
        ready = False

    payload = {"ready": ready, "service": "pipeline", "checks": checks}
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


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


class ScrapeRunRequest(BaseModel):
    triggered_by: str | None = None
    # Optional explicit seed window; when omitted the rotating cursor is used.
    seed_offset: int | None = None


def _scrape_run_public() -> dict[str, Any]:
    started = scrape_run_state.get("started_at")
    finished = scrape_run_state.get("finished_at")
    duration_ms: float | None = None
    if started is not None:
        end = finished if finished is not None else time.time()
        duration_ms = round((end - started) * 1000, 2)
    return {
        "job_id": scrape_run_state.get("job_id"),
        "status": scrape_run_state.get("status"),
        "started_at": started,
        "finished_at": finished,
        "duration_ms": duration_ms,
        "summary": scrape_run_state.get("summary"),
        "error": scrape_run_state.get("error"),
        "triggered_by": scrape_run_state.get("triggered_by"),
        "seed_offset": scrape_run_state.get("seed_offset"),
    }


async def _execute_scrape_run(job_id: str, seed_offset: int = 0) -> None:
    """Run one full scrape+embed+upsert cycle and record terminal state.

    A hard timeout guarantees the job can never sit in ``running`` forever: if
    the cycle stalls (slow/unreachable source, downstream hang), it transitions
    to ``failed`` so the admin UI stops polling and can retry.
    """
    try:
        summary = await asyncio.wait_for(
            _run_scrape_embedding_cycle(refresh_jobs=True, seed_offset=seed_offset),
            timeout=MANUAL_SCRAPE_TIMEOUT_SECONDS,
        )
        training_state["cycles"] += 1
        training_state["last_summary"] = summary
        training_state["last_finished_at"] = time.time()
        if scrape_run_state.get("job_id") == job_id:
            scrape_run_state.update(
                status="completed",
                finished_at=time.time(),
                summary=summary,
                error=None,
            )
    except asyncio.TimeoutError:
        logger.warning(
            "manual scrape run timed out job_id=%s after %ss",
            job_id,
            MANUAL_SCRAPE_TIMEOUT_SECONDS,
        )
        if scrape_run_state.get("job_id") == job_id:
            scrape_run_state.update(
                status="failed",
                finished_at=time.time(),
                error=f"scrape cycle timed out after {MANUAL_SCRAPE_TIMEOUT_SECONDS}s",
            )
    except Exception as exc:  # noqa: BLE001 - terminal state must capture any failure
        logger.exception("manual scrape run failed job_id=%s", job_id)
        if scrape_run_state.get("job_id") == job_id:
            scrape_run_state.update(
                status="failed",
                finished_at=time.time(),
                error=str(exc)[:300],
            )


@api.post("/pipeline/scrape-run", dependencies=[Depends(require_internal_service_token)])
async def pipeline_scrape_run(request: ScrapeRunRequest | None = None) -> dict[str, Any]:
    # Single-flight guard. The check+set runs without an intervening await, so
    # concurrent POSTs cannot both pass on the single-threaded event loop.
    if scrape_run_state.get("status") == "running":
        return {**_scrape_run_public(), "already_running": True}
    job_id = uuid.uuid4().hex
    override = request.seed_offset if request else None
    if override is not None:
        seed_offset = max(0, int(override)) % MANUAL_SCRAPE_SEED_MODULUS
    else:
        seed_offset = int(scrape_run_state.get("next_seed_offset") or 0) % MANUAL_SCRAPE_SEED_MODULUS
    next_offset = (seed_offset + MANUAL_SCRAPE_SEED_STRIDE) % MANUAL_SCRAPE_SEED_MODULUS
    scrape_run_state.update(
        job_id=job_id,
        status="running",
        started_at=time.time(),
        finished_at=None,
        summary=None,
        error=None,
        triggered_by=(request.triggered_by if request else None),
        seed_offset=seed_offset,
        next_seed_offset=next_offset,
    )
    asyncio.create_task(_execute_scrape_run(job_id, seed_offset))
    return {**_scrape_run_public(), "already_running": False}


@api.get("/pipeline/scrape-run/{job_id}", dependencies=[Depends(require_internal_service_token)])
async def pipeline_scrape_run_status(job_id: str) -> dict[str, Any]:
    if scrape_run_state.get("job_id") != job_id:
        raise HTTPException(status_code=404, detail="scrape job not found")
    return _scrape_run_public()


@api.post("/feedback", dependencies=[Depends(require_internal_service_token)])
async def feedback(request: FeedbackRequest) -> dict[str, Any]:
    if http_client is None:
        raise HTTPException(status_code=503, detail="pipeline not ready")
    profile = request.profile or {}
    skills = profile.get("skills") or []
    interests = profile.get("interests") or []
    profile_parts = [
        profile.get("name"),
        profile.get("program_studi") or profile.get("jurusan"),
        profile.get("jurusan"),
        *skills,
        *interests,
    ]
    profile_text = " ".join(str(part).strip() for part in profile_parts if str(part or "").strip())
    if not profile_text:
        profile_text = f"user {request.user_id}"
    texts = [profile_text]
    job_text = ""
    if request.job:
        job_text = " ".join(
            str(request.job.get(key) or "").strip()
            for key in ("title", "company", "description", "description_text", "tags", "required_skills")
            if str(request.job.get(key) or "").strip()
        )
        if job_text:
            texts.append(job_text)
    embeddings: list[Any] = []
    embedding_status = "ok"
    try:
        embed_response = await http_client.post(f"{SBERT_URL}/encode", json={"texts": texts})
        embed_response.raise_for_status()
        embeddings = embed_response.json().get("embeddings", [])
    except httpx.HTTPError as exc:
        embedding_status = "unavailable"
        logger.warning(
            "feedback embedding skipped user_id=%s job_id=%s text_count=%s error=%s",
            request.user_id,
            request.job_id,
            len(texts),
            exc,
        )
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
        "embedding_status": embedding_status,
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
