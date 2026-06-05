"""Backend contracts for the skill-gap detail surface."""

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
    email: str = "skill-gap-user@example.com",
    name: str = "Skill Gap User",
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _insert_user_skill(
    db_session: AsyncSession,
    user_id: str,
    skill: str,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO user_skills (user_id, skill, category, proficiency_level) "
            "VALUES (:user_id, :skill, 'technical', 'intermediate')"
        ),
        {"user_id": uuid.UUID(user_id), "skill": skill},
    )


async def _insert_job(
    db_session: AsyncSession,
    job_id: str,
    *,
    skills: list[str],
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO jobs ("
            "id, title, company, location, type, salary_currency, "
            "posted_at, is_active, match_data"
            ") VALUES ("
            ":id, 'Machine Learning Engineer', 'SCPA Test Lab', "
            "'Jakarta, Indonesia', 'full_time', 'IDR', NOW(), true, "
            "CAST(:match_data AS jsonb)"
            ")"
        ),
        {
            "id": uuid.UUID(job_id),
            "match_data": json.dumps(
                {"skills": skills, "source_url": "https://example.test/ml-job"}
            ),
        },
    )
    await db_session.commit()


async def _latest_skill_gap_snapshot(
    db_session: AsyncSession,
    user_id: str,
    job_id: str,
) -> dict[str, Any]:
    row = (
        await db_session.execute(
            text(
                "SELECT missing_skills, matched_skills, explanation "
                "FROM skill_gap_snapshots "
                "WHERE user_id = :user_id AND job_id = :job_id "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"user_id": uuid.UUID(user_id), "job_id": job_id},
        )
    ).mappings().one()
    return dict(row)


async def test_skill_gap_detail_requires_auth(client) -> None:
    response = await client.get(f"/api/jobs/{uuid.uuid4()}/skill-gap")

    assert response.status_code == 401


async def test_skill_gap_detail_returns_page_ready_contract_and_snapshot(
    client,
    db_session: AsyncSession,
) -> None:
    user = await _register(client)
    job_id = str(uuid.uuid4())
    await _insert_user_skill(db_session, user["user"]["id"], "Python")
    await _insert_user_skill(db_session, user["user"]["id"], "SQL")
    await _insert_job(db_session, job_id, skills=["Python", "SQL", "Docker"])

    response = await client.get(
        f"/api/jobs/{job_id}/skill-gap",
        headers=_auth_header(user["access_token"]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "job_id": job_id,
        "job_title": "Machine Learning Engineer",
        "company": "SCPA Test Lab",
        "required_skills": ["Docker", "Python", "SQL"],
        "matched_skills": ["Python", "SQL"],
        "missing_skills": ["Docker"],
        "skill_match_percent": 66.7,
        "explanation": {
            "matched_count": 2,
            "missing_count": 1,
            "required_count": 3,
            "summary": "2 of 3 required skills matched.",
        },
    }

    snapshot = await _latest_skill_gap_snapshot(
        db_session,
        user["user"]["id"],
        job_id,
    )
    assert snapshot["matched_skills"] == ["Python", "SQL"]
    assert snapshot["missing_skills"] == ["Docker"]
    assert snapshot["explanation"] == body["explanation"]


async def test_skill_gap_detail_returns_404_for_missing_job(client) -> None:
    user = await _register(client)

    response = await client.get(
        f"/api/jobs/{uuid.uuid4()}/skill-gap",
        headers=_auth_header(user["access_token"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
