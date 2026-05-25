"""Pipeline SBERT job embedding cache invalidation tests."""

from __future__ import annotations

import pytest

from services.pipeline.stages import stage_2_encode


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeClient:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.embeddings = embeddings
        self.requests: list[dict[str, object]] = []

    async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        self.requests.append({"url": url, "json": json})
        return FakeResponse(
            {
                "embeddings": self.embeddings,
                "model_name": "unit-sbert",
                "embedding_dim": len(self.embeddings[0]),
                "fallback_mode": False,
            }
        )


def _job() -> dict[str, object]:
    return {
        "id": "job-1",
        "title": "Backend Developer",
        "company": "Unit Co",
        "location": "Jakarta",
        "description": "Build Python APIs",
        "experience_level": "entry",
    }


@pytest.mark.anyio
async def test_encode_stage_reuses_cached_job_embedding_when_text_hash_matches() -> None:
    job = _job()
    cached_embedding = [0.0, 1.0]
    job["embedding"] = cached_embedding
    job["embedding_text_hash"] = stage_2_encode._job_text_hash(job)
    client = FakeClient(embeddings=[[1.0, 0.0]])

    result = await stage_2_encode.run_encode_stage(
        client,
        "http://sbert",
        {"profile_text": "Python backend"},
        [job],
    )

    assert client.requests[0]["json"] == {"texts": ["Python backend"]}
    assert result.jobs[0]["embedding"] == cached_embedding
    assert result.jobs[0]["embedding_text_hash"] == job["embedding_text_hash"]
    assert result.summary["job_embedding_cache_hits"] == 1
    assert result.summary["job_embedding_cache_misses"] == 0
    assert result.summary["used_cached_job_embeddings"] is True


@pytest.mark.anyio
async def test_encode_stage_recomputes_job_embedding_when_text_hash_changes() -> None:
    job = _job()
    job["embedding"] = [0.0, 1.0]
    job["embedding_text_hash"] = "old-text-hash"
    fresh_embedding = [0.7, 0.7]
    client = FakeClient(embeddings=[[1.0, 0.0], fresh_embedding])

    result = await stage_2_encode.run_encode_stage(
        client,
        "http://sbert",
        {"profile_text": "Python backend"},
        [job],
    )

    assert client.requests[0]["json"] == {
        "texts": ["Python backend", stage_2_encode._job_text(job)]
    }
    assert result.jobs[0]["embedding"] == fresh_embedding
    assert result.jobs[0]["embedding_text_hash"] == stage_2_encode._job_text_hash(job)
    assert result.summary["job_embedding_cache_hits"] == 0
    assert result.summary["job_embedding_cache_misses"] == 1
    assert result.summary["used_cached_job_embeddings"] is False
