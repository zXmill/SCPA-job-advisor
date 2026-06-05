"""E2E checks for the scriptable full SCPA pipeline entrypoint."""

from __future__ import annotations

import asyncio
from pathlib import Path

from scripts.run_full_pipeline import normalize_job, run_full_pipeline, validate_pipeline_jobs
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR


def test_normalize_job_allows_missing_optional_logo_and_skills() -> None:
    job = normalize_job(
        {
            "title": "Backend Developer",
            "company": "Tekno API",
            "location": "Remote Indonesia",
            "description": "Build FastAPI services.",
            "source_url": "https://example.com/jobs/backend",
        },
        source="scraper",
    )

    validation = validate_pipeline_jobs([job])

    assert validation["errors"] == []
    assert any("company_logo" in warning for warning in validation["warnings"])
    assert any("skills/tags" in warning for warning in validation["warnings"])
    assert job["job_id"]


def test_full_pipeline_entrypoint_writes_empty_real_data_reports_without_sample_jobs(tmp_path: Path) -> None:
    summary = asyncio.run(
        run_full_pipeline(
            sample_dir=DEFAULT_SAMPLE_DIR,
            artifact_dir=tmp_path / "artifacts",
            reports_dir=tmp_path / "reports",
            steps=1,
            limit=5,
            skip_scraper=True,
        )
    )

    assert summary["status"] == "empty_input"
    assert summary["dataset_status"] == "insufficient_for_generalization"
    assert summary["is_generalization_evidence"] is False
    assert summary["dataset"]["validation_errors"] == []
    assert summary["scraper"]["status"] == "skipped"
    assert summary["scraper"]["validation"]["errors"] == []
    assert summary["candidate_jobs"]["sample_jobs"] == 0
    assert summary["candidate_jobs"]["merged_jobs"] == 0
    assert summary["recommendations"] == {}
    assert (tmp_path / "reports" / "full_pipeline_summary.json").exists()
    assert (tmp_path / "reports" / "full_pipeline_metrics.csv").exists()
