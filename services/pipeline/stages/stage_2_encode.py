"""Stage 2: call SBERT semantic matching service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import hashlib
import math


@dataclass
class EncodeStageResult:
    jobs: list[dict[str, Any]]
    summary: dict[str, Any]


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "description", "experience_level")
    ).strip()


def _job_text_hash(job: dict[str, Any]) -> str:
    text = _job_text(job).strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    dot = sum(float(left[i]) * float(right[i]) for i in range(length))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left[:length]))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right[:length]))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    return max(0.0, min(1.0, (dot / (left_norm * right_norm) + 1.0) / 2.0))


async def run_encode_stage(
    client: httpx.AsyncClient,
    sbert_url: str,
    user: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> EncodeStageResult:
    job_texts = [_job_text(job) for job in jobs]
    job_text_hashes = [_job_text_hash(job) for job in jobs]
    cached_job_embeddings: list[list[float] | None] = []
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []
    for index, job in enumerate(jobs):
        embedding = job.get("embedding") or []
        if embedding and str(job.get("embedding_text_hash") or "") == job_text_hashes[index]:
            cached_job_embeddings.append(embedding)
            continue
        cached_job_embeddings.append(None)
        uncached_indices.append(index)
        uncached_texts.append(job_texts[index])

    texts = [user.get("profile_text") or "", *uncached_texts]
    embed_response = await client.post(f"{sbert_url.rstrip('/')}/encode", json={"texts": texts})
    embed_response.raise_for_status()
    embedding_data = embed_response.json()
    embeddings = embedding_data.get("embeddings", [])
    user_embedding = embeddings[0] if embeddings else []
    job_embeddings: list[list[float]] = [[] for _ in jobs]
    for index, embedding in enumerate(cached_job_embeddings):
        if embedding is not None:
            job_embeddings[index] = embedding
    fresh_embeddings = embeddings[1:] if len(embeddings) > 1 else []
    for offset, index in enumerate(uncached_indices):
        if offset < len(fresh_embeddings):
            job_embeddings[index] = fresh_embeddings[offset]
    score_by_index = {index: _cosine(user_embedding, embedding) for index, embedding in enumerate(job_embeddings)}
    enriched: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        enriched.append({
            **job,
            "sbert_score": score_by_index.get(index, 0.0),
            "embedding": job_embeddings[index] if index < len(job_embeddings) else [],
            "embedding_text_hash": job_text_hashes[index],
        })
    user["embedding"] = user_embedding
    cache_hits = len(jobs) - len(uncached_indices)
    return EncodeStageResult(
        jobs=enriched,
        summary={
            "scored": len(score_by_index),
            "embedded_jobs": len(job_embeddings),
            "model_version": embedding_data.get("model_version") or "embedding-cosine",
            "model_name": embedding_data.get("model_name"),
            "embedding_dim": embedding_data.get("embedding_dim"),
            "fallback_mode": bool(embedding_data.get("fallback_mode", False)),
            "fallback_flags": ["sbert_fallback"]
            if embedding_data.get("fallback_mode")
            else [],
            "used_cached_job_embeddings": bool(jobs) and not uncached_indices,
            "job_embedding_cache_hits": cache_hits,
            "job_embedding_cache_misses": len(uncached_indices),
        },
    )
