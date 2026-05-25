"""Backend contracts for saved jobs and skipped jobs."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = [pytest.mark.anyio, pytest.mark.db]


DEFAULT_PASSWORD = "Str0ng-Pass!word"


async def _register(
    client,
    *,
    email: str = "saved-user@example.com",
    name: str = "Saved User",
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _insert_job(
    db_session: AsyncSession,
    job_id: str,
    *,
    title: str = "Backend Developer",
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO jobs ("
            "id, title, company, location, type, salary_currency, "
            "posted_at, is_active, match_data"
            ") VALUES ("
            ":id, :title, 'SCPA Test', 'Jakarta, Indonesia', "
            "'full_time', 'IDR', NOW(), true, CAST(:match_data AS jsonb)"
            ")"
        ),
        {
            "id": uuid.UUID(job_id),
            "title": title,
            "match_data": json.dumps(
                {"skills": ["Python", "SQL"], "source_url": "https://example.test/job"}
            ),
        },
    )
    await db_session.commit()


async def _job_interaction_row(
    db_session: AsyncSession, user_id: str, job_id: str
) -> dict[str, Any]:
    row = (
        await db_session.execute(
            text(
                "SELECT saved, dismissed FROM user_job_interactions "
                "WHERE user_id = :uid AND job_id = :job_id"
            ),
            {"uid": uuid.UUID(user_id), "job_id": uuid.UUID(job_id)},
        )
    ).mappings().one()
    return dict(row)


async def test_save_job_requires_auth(client) -> None:
    response = await client.post(f"/api/jobs/{uuid.uuid4()}/save")

    assert response.status_code == 401


async def test_user_can_save_and_list_only_their_saved_jobs(
    client, db_session: AsyncSession
) -> None:
    first_user = await _register(client, email="saved-one@example.com")
    second_user = await _register(client, email="saved-two@example.com")
    job_id = str(uuid.uuid4())
    await _insert_job(db_session, job_id)

    save_response = await client.post(
        f"/api/jobs/{job_id}/save",
        headers=_auth_header(first_user["access_token"]),
    )
    assert save_response.status_code == 200, save_response.text
    assert save_response.json() == {"status": "saved", "job_id": job_id}

    first_list = await client.get(
        "/api/jobs/saved",
        headers=_auth_header(first_user["access_token"]),
    )
    second_list = await client.get(
        "/api/jobs/saved",
        headers=_auth_header(second_user["access_token"]),
    )

    assert first_list.status_code == 200, first_list.text
    first_body = first_list.json()
    assert first_body["total"] == 1
    assert first_body["jobs"][0]["id"] == job_id
    assert first_body["jobs"][0]["title"] == "Backend Developer"
    assert first_body["jobs"][0]["skills"] == ["Python", "SQL"]
    assert second_list.status_code == 200, second_list.text
    assert second_list.json() == {"jobs": [], "total": 0}
    assert await _job_interaction_row(db_session, first_user["user"]["id"], job_id) == {
        "saved": True,
        "dismissed": False,
    }


async def test_unsave_job_removes_it_from_saved_jobs(
    client, db_session: AsyncSession
) -> None:
    user = await _register(client)
    job_id = str(uuid.uuid4())
    await _insert_job(db_session, job_id)
    headers = _auth_header(user["access_token"])

    await client.post(f"/api/jobs/{job_id}/save", headers=headers)
    response = await client.delete(f"/api/jobs/{job_id}/save", headers=headers)
    saved_jobs = await client.get("/api/jobs/saved", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "unsaved", "job_id": job_id}
    assert saved_jobs.json() == {"jobs": [], "total": 0}
    assert await _job_interaction_row(db_session, user["user"]["id"], job_id) == {
        "saved": False,
        "dismissed": False,
    }


async def test_skip_job_marks_dismissed_and_clears_saved(
    client, db_session: AsyncSession
) -> None:
    user = await _register(client)
    job_id = str(uuid.uuid4())
    await _insert_job(db_session, job_id)
    headers = _auth_header(user["access_token"])

    await client.post(f"/api/jobs/{job_id}/save", headers=headers)
    response = await client.post(f"/api/jobs/{job_id}/skip", headers=headers)
    saved_jobs = await client.get("/api/jobs/saved", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "skipped", "job_id": job_id}
    assert saved_jobs.json() == {"jobs": [], "total": 0}
    assert await _job_interaction_row(db_session, user["user"]["id"], job_id) == {
        "saved": False,
        "dismissed": True,
    }
