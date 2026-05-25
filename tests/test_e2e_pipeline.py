"""End-to-end smoke tests for the local scraping + ML recommendation path."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.dqn.main import app as dqn_app
from services.ncf.main import app as ncf_app
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.sbert.main import app as sbert_app
from services.scraper.main import app as scraper_app


pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def _job_text(job: dict) -> str:
    return " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "description")
    )


async def test_scrape_to_ranked_recommendations_e2e() -> None:
    profile = {
        "id": "e2e-user",
        "program_studi": "Sastra Inggris",
        "interaction_count": 12,
        "profile_text": "Sastra Inggris Public Speaking translator content writer",
    }

    async with AsyncClient(
        transport=ASGITransport(app=scraper_app),
        base_url="http://scraper",
    ) as scraper:
        scrape_response = await scraper.get("/sample")
    assert scrape_response.status_code == 200
    jobs = scrape_response.json()["jobs"]
    assert len(jobs) >= 5
    assert all(job["job_id"] for job in jobs)
    assert all(job["company_logo"] for job in jobs)

    async with AsyncClient(
        transport=ASGITransport(app=sbert_app),
        base_url="http://sbert",
    ) as sbert:
        semantic_response = await sbert.post(
            "/match/semantic",
            json={
                "user_profile_text": profile["profile_text"],
                "job_descriptions": [_job_text(job) for job in jobs],
            },
        )
    assert semantic_response.status_code == 200
    sbert_by_index = {
        item["job_index"]: item["score"]
        for item in semantic_response.json()["scores"]
    }
    for index, job in enumerate(jobs):
        job["sbert_score"] = sbert_by_index[index]

    async with AsyncClient(
        transport=ASGITransport(app=ncf_app),
        base_url="http://ncf",
    ) as ncf:
        ncf_response = await ncf.post(
            "/recommend/ncf",
            json={
                "user_id": profile["id"],
                "profile_text": profile["profile_text"],
                "interaction_count": profile["interaction_count"],
                "n_items": len(jobs),
                "candidates": [
                    {
                        "id": job["content_hash"],
                        "title": job["title"],
                        "description": job["description"],
                        "tags": job["tags"],
                        "sbert_score": job["sbert_score"],
                    }
                    for job in jobs
                ],
            },
        )
    assert ncf_response.status_code == 200
    ncf_by_id = {
        item["job_id"]: item["score"]
        for item in ncf_response.json()["recommendations"]
    }
    for job in jobs:
        job["id"] = job["content_hash"]
        job["ncf_score"] = ncf_by_id[job["id"]]

    async with AsyncClient(
        transport=ASGITransport(app=dqn_app),
        base_url="http://dqn",
    ) as dqn:
        dqn_response = await dqn.post(
            "/rank",
            json={
                "user_id": profile["id"],
                "job_candidates": jobs,
                "session_ctx": {"interaction_count": profile["interaction_count"]},
            },
        )
    assert dqn_response.status_code == 200
    ranked = dqn_response.json()["ranked"]
    assert ranked
    q_values = [item["q_value"] for item in ranked]
    assert q_values == sorted(q_values, reverse=True)
    dqn_by_id = {item["job"]["id"]: item["q_value"] for item in ranked}
    for job in jobs:
        job["dqn_score"] = dqn_by_id[job["id"]]

    result = await run_aggregate_stage(profile, jobs)
    assert result.summary["strategy"] == "learned_logistic_calibrator_with_static_baseline"
    assert result.summary["calibrator"]["mode"] == "learned_logistic"
    assert len(result.ranked) == len(jobs)
    final_scores = [job["final_score"] for job in result.ranked]
    assert final_scores == sorted(final_scores, reverse=True)
    assert result.ranked[0]["company_logo"]
    assert "static_baseline_score" in result.ranked[0]
