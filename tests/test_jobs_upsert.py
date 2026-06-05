"""Unit and integration tests for recommended jobs database upserts and gateway routing."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.main import (
    _proxied_company_logo_url,
    clean_employment_mode,
    clean_experience_level,
    clean_job_source,
    clean_job_type,
    to_uuid,
)


def test_uuid_conversion_handles_uuids_and_hashes_correctly() -> None:
    """Verifies that to_uuid correctly parses real UUIDs and deterministically maps string hashes."""
    real_uuid = uuid.uuid4()
    assert to_uuid(str(real_uuid)) == real_uuid

    hash_id = "a8c094b13024c2ae"
    mapped_uuid_1 = to_uuid(hash_id)
    mapped_uuid_2 = to_uuid(hash_id)

    assert isinstance(mapped_uuid_1, uuid.UUID)
    assert mapped_uuid_1 == mapped_uuid_2
    assert mapped_uuid_1 != real_uuid


def test_clean_helpers_map_invalid_and_valid_values_gracefully() -> None:
    """Verifies that clean_job_type and other clean helpers correctly normalize string fields."""
    assert clean_job_type("Full-time") == "full_time"
    assert clean_job_type("intern") == "internship"
    assert clean_job_type("freelance") is None

    assert clean_employment_mode("on-site") == "onsite"
    assert clean_employment_mode("WFH") == "remote"
    assert clean_employment_mode("unknown") is None

    assert clean_experience_level("junior") == "entry"
    assert clean_experience_level("lead") == "senior"
    assert clean_experience_level("mid") == "mid"
    assert clean_experience_level("unknown") is None

    assert clean_job_source("LinkedIn") == "linkedin"
    assert clean_job_source("job-street") == "jobstreet"
    assert clean_job_source("monster") is None


def test_company_logo_proxy_allows_known_hosts_only() -> None:
    """Verifies company logos are served through the gateway or dropped to local fallback."""
    proxied = _proxied_company_logo_url(
        "https://media.licdn.com/dms/image/company-logo.png",
        "LinkedIn Company",
    )

    assert proxied is not None
    assert proxied.startswith("http://localhost:8000/api/company-logo?")
    assert "media.licdn.com" in proxied
    assert _proxied_company_logo_url("https://example.com/logo.png", "Unknown") is None


@pytest.mark.anyio
async def test_job_details_can_be_retrieved_by_arbitrary_hash_id(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verifies that inserting a job with mapped UUID allows fetching via original hash ID."""
    hash_id = "a8c094b13024c2ae"
    db_uuid = to_uuid(hash_id)

    # Insert a job using mapped UUID
    await db_session.execute(
        text(
            "INSERT INTO jobs (id, title, company, company_logo, location, type, salary_currency, is_active) "
            "VALUES (:id, :title, :company, :logo, :location, :type, :currency, :active)"
        ),
        {
            "id": db_uuid,
            "title": "Software Engineer Test",
            "company": "Test Company",
            "logo": "https://example.com/logo.png",
            "location": "Remote",
            "type": "full_time",
            "currency": "IDR",
            "active": True,
        },
    )
    await db_session.commit()

    # Query GET /api/jobs/{job_id} using the original hash ID
    resp = await client.get(f"/api/jobs/{hash_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == hash_id
    assert data["title"] == "Software Engineer Test"
    assert data["company"] == "Test Company"
    assert data["company_logo"] is None


@pytest.mark.anyio
async def test_applying_to_job_with_hash_id_maps_uuid_successfully(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Verifies that submitting an application with a hash ID resolves to the mapped UUID in DB."""
    # 1. Create a user
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, name, email, password_hash, role) "
            "VALUES (:id, 'Test User', 'testapp@example.com', 'hash', 'user')"
        ),
        {"id": user_id, "role": "user"},
    )

    # 2. Create the job in DB using mapped UUID
    hash_id = "b7d185c24135d3bf"
    db_uuid = to_uuid(hash_id)
    await db_session.execute(
        text(
            "INSERT INTO jobs (id, title, company, salary_currency, is_active) "
            "VALUES (:id, 'Job Title', 'Job Company', 'IDR', True)"
        ),
        {"id": db_uuid},
    )
    await db_session.commit()

    # 3. Form authorization header (HS256)
    # Using a dummy credentials token for testing (ASGITransport doesn't verify signatures in the same way,
    # or we can mock _get_current_user / inject headers using client)
    import jwt as pyjwt
    import os
    from datetime import datetime, timedelta, timezone

    secret = os.environ.get("JWT_SECRET", "test-secret-32-bytes-long-key!!!")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": "user",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Call POST /api/applications with original hash ID
    resp = await client.post(
        "/api/applications",
        json={"job_ids": [hash_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["created"] == 1

    # 5. Verify database application row has mapped job_id
    rows = (
        await db_session.execute(
            text("SELECT user_id, job_id, status FROM applications WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).mappings().all()

    assert len(rows) == 1
    assert rows[0]["job_id"] == db_uuid
    assert rows[0]["user_id"] == user_id
    assert rows[0]["status"] == "submitted"
