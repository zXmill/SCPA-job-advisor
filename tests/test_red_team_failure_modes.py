"""Failure-mode regression checks for the thesis/demo pipeline."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_full_pipeline import run_full_pipeline
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR
from services.dqn.main import OnlineDQN, app as dqn_app
from services.ncf.main import CandidateJob, OnlineNCF
from services.scraper.main import app as scraper_app, extract_jobs_from_json


def _copy_sample(tmp_path: Path) -> Path:
    sample_dir = tmp_path / "sample"
    shutil.copytree(DEFAULT_SAMPLE_DIR, sample_dir)
    return sample_dir


def test_full_pipeline_handles_empty_users_without_crashing(tmp_path: Path) -> None:
    sample_dir = _copy_sample(tmp_path)
    (sample_dir / "users.jsonl").write_text("", encoding="utf-8")

    summary = asyncio.run(
        run_full_pipeline(
            sample_dir=sample_dir,
            artifact_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            steps=1,
            limit=3,
        )
    )

    assert summary["status"] == "empty_input"
    assert summary["recommendations"] == {}
    assert Path(tmp_path / "reports" / "full_pipeline_summary.json").exists()


def test_full_pipeline_flags_invalid_interactions_but_still_exports_reports(tmp_path: Path) -> None:
    sample_dir = _copy_sample(tmp_path)
    (sample_dir / "interactions.jsonl").write_text(
        '{"user_id":"missing-user","job_id":"missing-job","event":"click","label":1.0}\n',
        encoding="utf-8",
    )

    summary = asyncio.run(
        run_full_pipeline(
            sample_dir=sample_dir,
            artifact_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            steps=1,
            limit=3,
        )
    )

    assert summary["status"] == "check"
    assert any("unknown user" in blocker for blocker in summary["blockers"])
    assert any("unknown job" in blocker for blocker in summary["blockers"])
    assert Path(summary["reports"]["metrics_csv"]).exists()
    assert Path(summary["reports"]["recommendations_json"]).exists()


def test_full_pipeline_refuses_sample_job_fallback_when_scraper_is_skipped(tmp_path: Path) -> None:
    sample_dir = _copy_sample(tmp_path)

    summary = asyncio.run(
        run_full_pipeline(
            sample_dir=sample_dir,
            artifact_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            steps=1,
            limit=3,
            skip_scraper=True,
        )
    )

    assert summary["status"] == "empty_input"
    assert summary["scraper"]["status"] == "skipped"
    assert summary["candidate_jobs"]["scraped_jobs"] == 0
    assert summary["candidate_jobs"]["merged_jobs"] == 0
    assert summary["recommendations"] == {}


def test_scraper_handles_zero_partial_duplicate_and_blocked_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_INDONESIA_ONLY", "false")
    client = TestClient(scraper_app)

    zero = client.post(
        "/scrape/html",
        json={"html": "<html><body>No jobs here</body></html>", "source_url": "https://example.com/none"},
    )
    assert zero.status_code == 200
    zero_payload = zero.json()
    assert zero_payload["count"] == 0
    assert zero_payload["jobs"] == []
    assert zero_payload["deduplicated"] == 0

    partial_html = """
    <article class="job-card"><h2>Data Wizard</h2><div class="company">NoLogo Co</div><p>short</p></article>
    <article class="job-card"><h2>Data Wizard</h2><div class="company">NoLogo Co</div><p>duplicate</p></article>
    <article class="job-card"><h2>Untethered Role</h2></article>
    """
    partial = client.post("/scrape/html", json={"html": partial_html, "limit": 10})
    assert partial.status_code == 200
    payload = partial.json()
    assert payload["count"] == 2
    assert payload["deduplicated"] == 1
    assert payload["jobs"][0]["company_logo"]

    blocked = client.post("/scrape/url", json={"url": "http://127.0.0.1:9/nope", "limit": 5})
    assert blocked.status_code == 400
    assert "private or non-public" in blocked.json()["detail"]


def test_scraper_normalizes_public_job_api_payload_with_logo_and_deduplication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_INDONESIA_ONLY", "false")
    payload = {
        "jobs": [
            {
                "id": 123,
                "url": "https://remotive.com/remote-jobs/software/dev-123",
                "title": "Python Backend Engineer",
                "company_name": "Remote API Co",
                "company_logo": "https://remotive.com/job/123/logo",
                "candidate_required_location": "Worldwide",
                "description": "<p>Build FastAPI services with Python and PostgreSQL.</p>",
                "tags": ["Python", "FastAPI", "PostgreSQL"],
            },
            {
                "id": 124,
                "url": "https://remotive.com/remote-jobs/software/dev-124",
                "title": "Python Backend Engineer",
                "company_name": "Remote API Co",
                "company_logo": "https://remotive.com/job/124/logo",
                "candidate_required_location": "Worldwide",
                "description": "<p>Duplicate role.</p>",
                "tags": ["Python"],
            },
        ]
    }

    result = extract_jobs_from_json(payload, source_url="https://remotive.com/api/remote-jobs", limit=10)

    assert result.count == 1
    assert result.deduplicated == 1
    job = result.jobs[0].model_dump()
    assert job["title"] == "Python Backend Engineer"
    assert job["company"] == "Remote API Co"
    assert job["location"] == "Worldwide"
    assert job["company_logo"] == "https://remotive.com/job/123/logo"
    assert job["source_url"] == "https://remotive.com/remote-jobs/software/dev-123"
    assert job["description"] == "Build FastAPI services with Python and PostgreSQL."
    assert job["skills"] == ["Python", "FastAPI", "PostgreSQL"]


def test_scraper_normalizes_kalibrr_indonesia_next_payload_with_logo() -> None:
    payload = {
        "props": {
            "pageProps": {
                "jobs": [
                    {
                        "id": 266592,
                        "name": "Tutor Freelance Bahasa Indonesia",
                        "slug": "tutor-freelance-bahasa-indonesia",
                        "companyName": "CV. Assyifa Learning Center",
                        "company": {
                            "code": "cv-assyifa-learning-center",
                            "industry": "Education Management",
                            "logoSmall": "https://rec-data.kalibrr.com/www.kalibrr.com/logos/logo.png",
                            "name": "CV. Assyifa Learning Center",
                        },
                        "googleLocation": {
                            "addressComponents": {
                                "city": "Subang",
                                "region": "West Java (Jawa Barat)",
                                "country": "Indonesia",
                            }
                        },
                        "description": "<p>Mengampu mata pelajaran Bahasa Indonesia.</p>",
                    }
                ]
            }
        }
    }

    result = extract_jobs_from_json(payload, source_url="https://www.kalibrr.com/home/te/indonesia", limit=10)

    assert result.count == 1
    job = result.jobs[0].model_dump()
    assert job["title"] == "Tutor Freelance Bahasa Indonesia"
    assert job["company"] == "CV. Assyifa Learning Center"
    assert job["location"] == "Subang, West Java (Jawa Barat), Indonesia"
    assert job["company_logo"] == "https://rec-data.kalibrr.com/www.kalibrr.com/logos/logo.png"
    assert job["source_url"] == "https://www.kalibrr.com/c/cv-assyifa-learning-center/jobs/266592/tutor-freelance-bahasa-indonesia"
    assert job["description"] == "Mengampu mata pelajaran Bahasa Indonesia."


def test_scraper_rejects_global_remote_jobs_when_indonesia_only() -> None:
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "company_name": "Global Remote Co",
                "candidate_required_location": "United States",
                "description": "Remote backend role for US candidates.",
                "url": "https://remotive.com/remote-jobs/software/backend",
            }
        ]
    }

    result = extract_jobs_from_json(payload, source_url="https://remotive.com/api/remote-jobs", limit=10)

    assert result.count == 0
    assert result.jobs == []


def test_corrupted_model_artifacts_do_not_break_prediction(tmp_path: Path) -> None:
    bad_ncf = tmp_path / "bad_ncf.json"
    bad_ncf.write_text("{not-json", encoding="utf-8")
    ncf = OnlineNCF(model_path=bad_ncf, autosave=False, load_existing=True)
    ncf.upsert_jobs([CandidateJob(id="job-new", title="Backend", description="python api")])
    assert 0.0 <= ncf.predict_one("unseen-user", "job-new") <= 1.0

    bad_dqn = tmp_path / "bad_dqn.json"
    bad_dqn.write_text("{not-json", encoding="utf-8")
    dqn = OnlineDQN(model_path=bad_dqn, autosave=False, load_existing=True)
    ranked = dqn.rank("unseen-user", [{"job_id": "job-new", "title": "Backend"}], {})
    assert len(ranked) == 1
    assert isinstance(ranked[0]["q_value"], float)


def test_dqn_empty_candidates_and_unknown_role_are_safe() -> None:
    client = TestClient(dqn_app)

    empty = client.post("/rank", json={"user_id": "u", "job_candidates": [], "session_ctx": {}})
    assert empty.status_code == 200
    assert empty.json()["ranked_jobs"] == []

    unknown = client.post(
        "/learning-path",
        json={"user_id": "u", "current_skills": [], "target_role": "Unknown Role"},
    )
    assert unknown.status_code == 410
