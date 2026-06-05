"""End-to-end smoke tests for the local scraping + ML recommendation path."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.dqn.main import app as dqn_app
from services.ncf.main import app as ncf_app
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.sbert.main import app as sbert_app
from services.scraper.main import app as scraper_app
from tests.test_job_description_quality import CBI_DESCRIPTION


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
        scrape_response = await scraper.post(
            "/scrape/html",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/cbi-data-scientist",
                "html": f"""
                    <article class="job-card">
                      <h2 class="job-title">Data Scientist</h2>
                      <div class="company">CBI Credit Bureau Indonesia</div>
                      <div class="location">South Jakarta, Indonesia</div>
                      <p class="description">{CBI_DESCRIPTION}</p>
                      <span class="tag">Python</span>
                      <span class="tag">MLOps</span>
                      <span class="tag">Credit Scoring</span>
                      <span class="tag">Docker</span>
                      <span class="tag">Kubernetes</span>
                    </article>
                    <article class="job-card">
                      <h2 class="job-title">Data Platform Engineer</h2>
                      <div class="company">CBI Credit Bureau Indonesia</div>
                      <div class="location">Jakarta, Indonesia</div>
                      <p class="description">{CBI_DESCRIPTION}</p>
                      <span class="tag">Airflow</span>
                      <span class="tag">Git</span>
                    </article>
                    <article class="job-card">
                      <h2 class="job-title">Machine Learning Engineer</h2>
                      <div class="company">CBI Credit Bureau Indonesia</div>
                      <div class="location">Jakarta, Indonesia</div>
                      <p class="description">{CBI_DESCRIPTION}</p>
                      <span class="tag">Machine Learning</span>
                    </article>
                    <article class="job-card">
                      <h2 class="job-title">MLOps Engineer</h2>
                      <div class="company">CBI Credit Bureau Indonesia</div>
                      <div class="location">Jakarta, Indonesia</div>
                      <p class="description">{CBI_DESCRIPTION}</p>
                      <span class="tag">MLOps</span>
                    </article>
                    <article class="job-card">
                      <h2 class="job-title">Credit Risk Data Scientist</h2>
                      <div class="company">CBI Credit Bureau Indonesia</div>
                      <div class="location">Jakarta, Indonesia</div>
                      <p class="description">{CBI_DESCRIPTION}</p>
                      <span class="tag">Credit Scoring</span>
                    </article>
                """,
                "limit": 10,
            },
        )
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
    ranked = dqn_response.json()["ranked_jobs"]
    assert ranked
    final_scores = [item["final_score"] for item in ranked]
    assert final_scores == sorted(final_scores, reverse=True)
    dqn_by_id = {item["job"]["id"]: item["dqn_session_score"] for item in ranked}
    for job in jobs:
        job["dqn_score"] = dqn_by_id[job["id"]]

    result = await run_aggregate_stage(profile, jobs)
    assert result.summary["strategy"] == "transparent_alpha_beta_gamma_hybrid_with_separate_calibration"
    assert result.summary["calibrator"]["mode"] == "learned_logistic"
    assert result.summary["scoring_formula"] == "final_score = alpha*sbert_score + beta*ncf_score + gamma*dqn_session_score"
    assert result.summary["weights_sum"] == 1.0
    assert len(result.ranked) == len(jobs)
    final_scores = [job["final_score"] for job in result.ranked]
    assert final_scores == sorted(final_scores, reverse=True)
    assert result.ranked[0]["company_logo"]
    assert "static_baseline_score" in result.ranked[0]
    assert {"alpha", "beta", "gamma", "calibrated_score", "calibration_note"} <= set(result.ranked[0])
