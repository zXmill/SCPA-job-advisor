"""Backend contracts for global job catalog filtering and facets."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.anyio, pytest.mark.db]


async def _insert_job(
    db_session: AsyncSession,
    *,
    title: str,
    location: str,
    company: str = "SCPA Test",
    job_type: str = "full_time",
    job_field: str = "Technology",
    industry: str | None = None,
    employment_mode: str | None = "onsite",
    description: str = "Role for backend and data work.",
    posted_days_ago: int = 0,
    is_active: bool = True,
    quality_status: str = "accepted",
) -> str:
    job_id = str(uuid.uuid4())
    posted_at = datetime.now() - timedelta(days=posted_days_ago)
    await db_session.execute(
        text(
            "INSERT INTO jobs ("
            "id, title, company, location, type, salary_currency, employment_mode, "
            "description, description_text, job_function, industry, posted_at, "
            "source, is_active, quality_status, match_data"
            ") VALUES ("
            ":id, :title, :company, :location, :job_type, 'IDR', :employment_mode, "
            ":description, :description, :job_field, :industry, :posted_at, "
            "'kalibrr', :is_active, :quality_status, CAST(:match_data AS jsonb)"
            ")"
        ),
        {
            "id": uuid.UUID(job_id),
            "title": title,
            "company": company,
            "location": location,
            "job_type": job_type,
            "employment_mode": employment_mode,
            "description": description,
            "job_field": job_field,
            "industry": industry,
            "posted_at": posted_at,
            "is_active": is_active,
            "quality_status": quality_status,
            "match_data": json.dumps({"skills": ["Python", "SQL"]}),
        },
    )
    await db_session.commit()
    return job_id


def _facet_counts(body: dict[str, Any], key: str) -> dict[str, int]:
    return {item["value"]: item["count"] for item in body[key]}


async def test_jobs_location_filter_applies_before_pagination(
    client,
    db_session: AsyncSession,
) -> None:
    for index in range(30):
        await _insert_job(
            db_session,
            title=f"Jakarta Backend {index}",
            location="Jakarta, Indonesia",
            posted_days_ago=index,
        )
    target_id = await _insert_job(
        db_session,
        title="Bandung Backend",
        location="Bandung, Indonesia",
        posted_days_ago=90,
    )

    response = await client.get(
        "/api/jobs",
        params={"page": 1, "limit": 25, "location": "Bandung"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 31
    assert body["total_filtered"] == 1
    assert body["total_pages"] == 1
    assert [item["id"] for item in body["items"]] == [target_id]
    assert body["jobs"] == body["items"]


async def test_jobs_facets_count_full_catalog_not_current_page(
    client,
    db_session: AsyncSession,
) -> None:
    for index in range(30):
        await _insert_job(
            db_session,
            title=f"Jakarta Data {index}",
            location="Jakarta, Indonesia",
            job_field="Data",
            posted_days_ago=index,
        )
    await _insert_job(
        db_session,
        title="Surabaya Finance",
        location="Surabaya, Indonesia",
        job_field="Finance",
        job_type="contract",
        posted_days_ago=80,
    )

    page_response = await client.get("/api/jobs", params={"page": 1, "limit": 25})
    facets_response = await client.get("/api/jobs/facets")

    assert page_response.status_code == 200, page_response.text
    assert len(page_response.json()["items"]) == 25
    assert facets_response.status_code == 200, facets_response.text
    facets = facets_response.json()
    location_counts = _facet_counts(facets, "locations")
    field_counts = _facet_counts(facets, "job_fields")
    assert location_counts["Jakarta, Indonesia"] == 30
    assert location_counts["Surabaya, Indonesia"] == 1
    assert field_counts["data"] == 30
    assert field_counts["finance"] == 1
    assert facets["policy"] == "contextual"


async def test_jobs_salary_param_is_ignored_by_filter_contract(
    client,
    db_session: AsyncSession,
) -> None:
    await _insert_job(db_session, title="Backend", location="Jakarta, Indonesia")
    await _insert_job(db_session, title="Frontend", location="Bandung, Indonesia")

    response = await client.get(
        "/api/jobs",
        params={"salary": "40000000", "page": 1, "limit": 25},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_filtered"] == 2
    assert body["filters_applied"] == {
        "time_range": None,
        "job_type": [],
        "job_field": [],
        "location": [],
        "work_mode": [],
    }


async def test_jobs_work_mode_filter_supports_remote_onsite_hybrid(
    client,
    db_session: AsyncSession,
) -> None:
    remote_id = await _insert_job(
        db_session,
        title="Remote Analyst",
        location="Remote Indonesia",
        employment_mode=None,
        description="Work from home role for Indonesia-based candidates.",
    )
    await _insert_job(
        db_session,
        title="Office Analyst",
        location="Jakarta, Indonesia",
        employment_mode=None,
        description="Bekerja di kantor Jakarta.",
    )
    await _insert_job(
        db_session,
        title="Hybrid Analyst",
        location="Tangerang, Indonesia",
        employment_mode="hybrid",
        description="Hybrid team schedule.",
    )

    filtered = await client.get("/api/jobs", params={"work_mode": "remote"})
    facets = await client.get("/api/jobs/facets")

    assert filtered.status_code == 200, filtered.text
    body = filtered.json()
    assert body["total_filtered"] == 1
    assert body["items"][0]["id"] == remote_id

    assert facets.status_code == 200, facets.text
    counts = _facet_counts(facets.json(), "work_modes")
    assert counts["remote"] == 1
    assert counts["onsite"] == 1
    assert counts["hybrid"] == 1


async def test_jobs_invalid_filter_is_controlled_and_empty_result_is_200(
    client,
    db_session: AsyncSession,
) -> None:
    await _insert_job(db_session, title="Backend", location="Jakarta, Indonesia")

    invalid = await client.get("/api/jobs", params={"job_type": "not-a-contract"})
    empty = await client.get("/api/jobs", params={"location": "Tidak Ada Kota"})

    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["total_filtered"] == 1
    assert invalid.json()["filters_applied"]["job_type"] == []
    assert empty.status_code == 200, empty.text
    assert empty.json()["items"] == []
    assert empty.json()["total_filtered"] == 0
    assert empty.json()["total_pages"] == 1


async def test_jobs_catalog_hides_expired_listings_when_max_age_set(
    client,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The freshness ceiling must hide stale jobs from the catalog, facets, and
    counts — including the "all time" range — so expired scrapes never surface."""
    import services.gateway.main as gateway_main

    monkeypatch.setattr(gateway_main, "JOB_CATALOG_MAX_AGE_DAYS", 90)

    fresh_id = await _insert_job(
        db_session,
        title="Fresh Backend",
        location="Jakarta, Indonesia",
        posted_days_ago=10,
    )
    await _insert_job(
        db_session,
        title="Stale Backend",
        location="Jakarta, Indonesia",
        posted_days_ago=200,
    )

    listing = await client.get("/api/jobs", params={"page": 1, "limit": 25})
    facets = await client.get("/api/jobs/facets")

    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total_filtered"] == 1
    assert [item["id"] for item in body["items"]] == [fresh_id]

    assert facets.status_code == 200, facets.text
    time_counts = {item["value"]: item["count"] for item in facets.json()["time_ranges"]}
    # The "all" bucket must also exclude the expired listing.
    assert time_counts["all"] == 1


async def test_jobs_catalog_shows_all_ages_when_max_age_disabled(
    client,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the ceiling disabled (0), old jobs are no longer hidden."""
    import services.gateway.main as gateway_main

    monkeypatch.setattr(gateway_main, "JOB_CATALOG_MAX_AGE_DAYS", 0)

    await _insert_job(
        db_session,
        title="Fresh Backend",
        location="Jakarta, Indonesia",
        posted_days_ago=10,
    )
    await _insert_job(
        db_session,
        title="Stale Backend",
        location="Jakarta, Indonesia",
        posted_days_ago=200,
    )

    listing = await client.get("/api/jobs", params={"page": 1, "limit": 25})
    assert listing.status_code == 200, listing.text
    assert listing.json()["total_filtered"] == 2
