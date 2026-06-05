"""Regression coverage for gateway API runtime guard failures found by probes."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import services.gateway.main as gateway_main


pytestmark = [pytest.mark.anyio, pytest.mark.db]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={
            "name": "API Runtime Guard User",
            "email": "api-runtime-guard@example.com",
            "password": "Str0ng-Pass!word",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_applying_to_missing_job_returns_404(client) -> None:
    """Invalid application job IDs must not leak database FK errors as HTTP 500."""
    user = await _register(client)

    response = await client.post(
        "/api/applications",
        json={"job_ids": [str(uuid.uuid4())]},
        headers=_auth_header(user["access_token"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


async def test_upsert_jobs_accepts_iso_posted_at_strings(
    db_session: AsyncSession,
) -> None:
    """Pipeline JSON timestamps arrive as strings and must persist as datetimes."""
    job_id = str(uuid.uuid4())

    await gateway_main._upsert_jobs_to_db(
        db_session,
        [
            {
                "id": job_id,
                "title": "Runtime Probe Analyst",
                "company": "SCPA Test",
                "location": "Jakarta, Indonesia",
                "posted_at": "2026-05-31T02:05:03.063175",
                "source": "linkedin",
                "is_active": True,
            }
        ],
    )

    row = (
        await db_session.execute(
            text("SELECT id, posted_at FROM jobs WHERE id = :id"),
            {"id": uuid.UUID(job_id)},
        )
    ).mappings().first()

    assert row is not None
    assert row["posted_at"].isoformat().startswith("2026-05-31T02:05:03")
