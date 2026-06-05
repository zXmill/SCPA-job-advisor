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
    parts: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for nested in value.values():
                add(nested)
            return
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                add(nested)
            return
        text = str(value).strip()
        if text:
            parts.append(text)

    for key in (
        "title",
        "company",
        "location",
        "job_function",
        "industry",
        "seniority_level",
        "employment_type",
        "experience_level",
        "description_text",
        "description",
        "description_sections",
        "responsibilities",
        "requirements",
        "nice_to_have",
        "required_skills",
        "required_skill_names",
        "preferred_skills",
        "preferred_skill_names",
        "extracted_skills",
        "extracted_skill_names",
        "skills",
        "tags",
    ):
        add(job.get(key))

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(part)
    return " ".join(deduped).strip()


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


def _as_job_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _as_job_id(value.get("job_id") or value.get("id"))
    text = str(value).strip()
    return text or None


def _extract_ground_truth_job_ids(user: dict[str, Any]) -> set[str]:
    relevant: set[str] = set()
    for key in (
        "ground_truth_job_ids",
        "relevant_job_ids",
        "positive_job_ids",
        "liked_job_ids",
        "applied_job_ids",
    ):
        value = user.get(key)
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple, set)) else [value]
        for item in values:
            job_id = _as_job_id(item)
            if job_id:
                relevant.add(job_id)

    interactions = user.get("interactions") or user.get("interaction_history") or []
    if isinstance(interactions, dict):
        interactions = interactions.values()
    for interaction in interactions:
        if not isinstance(interaction, dict):
            continue
        event = str(interaction.get("event") or interaction.get("type") or "").lower()
        label = interaction.get("label", interaction.get("reward"))
        is_positive = event in {"apply", "applied", "click", "save", "saved", "like", "liked"}
        try:
            is_positive = is_positive or float(label) > 0.0
        except (TypeError, ValueError):
            pass
        if is_positive:
            job_id = _as_job_id(interaction.get("job_id") or interaction.get("id"))
            if job_id:
                relevant.add(job_id)
    return relevant


def _recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def _dcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    score = 0.0
    for index, job_id in enumerate(ranked_ids[:k], start=1):
        if job_id in relevant_ids:
            score += 1.0 / math.log2(index + 1)
    return score


def _ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    ideal_hits = min(len(relevant_ids), k)
    if ideal_hits <= 0:
        return 0.0
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return _dcg_at_k(ranked_ids, relevant_ids, k) / ideal if ideal > 0.0 else 0.0


def _mrr_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    for index, job_id in enumerate(ranked_ids[:k], start=1):
        if job_id in relevant_ids:
            return 1.0 / index
    return 0.0


def _map_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, job_id in enumerate(ranked_ids[:k], start=1):
        if job_id in relevant_ids:
            hits += 1
            precision_sum += hits / index
    denominator = min(len(relevant_ids), k)
    return precision_sum / denominator if denominator else 0.0


def _semantic_metrics(ranked_ids: list[str], relevant_ids: set[str]) -> dict[str, Any]:
    if not relevant_ids:
        return {
            "metrics_status": "not_computed_no_ground_truth",
            "missing_data": [
                "relevant job ids from labels, positive interactions, applications, saves, or clicks"
            ],
        }
    return {
        "metrics_status": "computed",
        "relevant_job_count": len(relevant_ids),
        "Recall@50": round(_recall_at_k(ranked_ids, relevant_ids, 50), 6),
        "Recall@100": round(_recall_at_k(ranked_ids, relevant_ids, 100), 6),
        "NDCG@10": round(_ndcg_at_k(ranked_ids, relevant_ids, 10), 6),
        "NDCG@50": round(_ndcg_at_k(ranked_ids, relevant_ids, 50), 6),
        "MRR@10": round(_mrr_at_k(ranked_ids, relevant_ids, 10), 6),
        "MAP@100": round(_map_at_k(ranked_ids, relevant_ids, 100), 6),
    }


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
    enriched_unsorted: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        job_id = str(job.get("job_id") or job.get("id"))
        enriched_unsorted.append({
            **job,
            "job_id": job_id,
            "sbert_score": score_by_index.get(index, 0.0),
            "embedding": job_embeddings[index] if index < len(job_embeddings) else [],
            "embedding_text": job_texts[index],
            "embedding_text_hash": job_text_hashes[index],
            "candidate_pool_source": "sbert_top_m",
        })
    enriched = sorted(
        enriched_unsorted,
        key=lambda item: float(item.get("sbert_score") or 0.0),
        reverse=True,
    )
    candidate_pool_size = len(enriched)
    for semantic_rank, job in enumerate(enriched, start=1):
        job["semantic_rank"] = semantic_rank
        job["candidate_pool_size"] = candidate_pool_size

    user["embedding"] = user_embedding
    cache_hits = len(jobs) - len(uncached_indices)
    ranked_ids = [str(job.get("job_id") or job.get("id")) for job in enriched]
    semantic_metrics = _semantic_metrics(ranked_ids, _extract_ground_truth_job_ids(user))
    embedding_model = (
        embedding_data.get("model_name")
        or embedding_data.get("model_version")
        or "embedding-cosine"
    )
    return EncodeStageResult(
        jobs=enriched,
        summary={
            "stage_name": "sbert_semantic_candidate_generator",
            "top_m": candidate_pool_size,
            "input_job_count": len(jobs),
            "output_candidate_count": candidate_pool_size,
            "candidate_pool_source": "sbert_top_m",
            "embedding_model": embedding_model,
            "semantic_metrics": semantic_metrics,
            "metrics_status": semantic_metrics["metrics_status"],
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
