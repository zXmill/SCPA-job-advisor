"""Regression tests for continuous scraper job identity and metadata."""

from __future__ import annotations

from services.pipeline.stages.stage_1_scrape import (
    _job_identity_key,
    _normalize_scraped_jobs,
    _payload_content_hash,
    _stable_uuid,
)


def test_job_identity_prefers_normalized_source_url() -> None:
    """Repeated cycles for the same external posting must map to one DB row."""
    first = {
        "job_id": "old-list-card-hash",
        "source": "kalibrr",
        "source_url": "https://www.kalibrr.com/c/acme/jobs/123/data-scientist?utm_source=x#apply",
        "title": "Data Scientist",
        "company": "ACME",
        "location": "Jakarta, Indonesia",
    }
    second = {
        **first,
        "job_id": "new-list-card-hash",
        "source_url": "https://www.kalibrr.com/c/acme/jobs/123/data-scientist",
    }

    assert _job_identity_key(first) == _job_identity_key(second)
    assert _stable_uuid(_job_identity_key(first)) == _stable_uuid(_job_identity_key(second))


def test_content_hash_changes_when_job_payload_changes() -> None:
    """The continuous metadata hash tracks real payload changes separately from identity."""
    base = {
        "title": "Data Scientist",
        "company": "ACME",
        "location": "Jakarta",
        "description_text": "Build machine learning systems with Python and SQL.",
        "required_skills": ["Python", "SQL"],
    }
    changed = {
        **base,
        "description_text": "Build machine learning systems with Python, SQL, Docker, and Kubernetes.",
    }

    assert _payload_content_hash(base) != _payload_content_hash(changed)
    assert _payload_content_hash(base) == _payload_content_hash(dict(base))


def test_normalize_scraped_jobs_does_not_promote_source_tags_to_required_skills() -> None:
    jobs = _normalize_scraped_jobs(
        [
            {
                "id": "kalibrr-1",
                "title": "Hub Mitra Training & Program Supervisor",
                "company": "Astro",
                "description": "Training operations and reporting role.",
                "tags": ["E-Commerce"],
                "skills": ["E-Commerce"],
                "extracted_skills": ["Training", "Operations", "Reporting"],
            }
        ],
        limit=1,
    )

    assert jobs[0]["required_skills"] == []
    assert jobs[0]["extracted_skills"] == ["Training", "Operations", "Reporting"]
    assert jobs[0]["skills"] == ["Training", "Operations", "Reporting"]
