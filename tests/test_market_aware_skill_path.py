"""Tests for market-aware skill path recommender."""

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.anyio, pytest.mark.db]

DEFAULT_PASSWORD = "Str0ng-Pass!word"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(
    client,
    *,
    email: str = "market-user@example.com",
    name: str = "Market User",
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _insert_job_with_skills(db_session: AsyncSession) -> None:
    """Seed jobs and job_required_skills for market demand computation."""
    skills = [
        ("Python", "technical", ["python", "py"]),
        ("SQL", "technical", ["sql"]),
        ("Docker", "technical", ["docker"]),
    ]
    skill_ids = {}
    for name, category, aliases in skills:
        result = await db_session.execute(
            text(
                "INSERT INTO skills (name, category, aliases) "
                "VALUES (:name, :category, :aliases) "
                "ON CONFLICT (name) DO UPDATE SET category = EXCLUDED.category "
                "RETURNING id"
            ),
            {"name": name, "category": category, "aliases": aliases},
        )
        skill_ids[name] = result.scalar_one()

    job_ids = {
        "job-1": str(uuid.uuid4()),
        "job-2": str(uuid.uuid4()),
        "job-3": str(uuid.uuid4()),
    }
    jobs = [
        ("job-1", "Backend Engineer", "Acme Corp", "jakarta"),
        ("job-2", "Data Analyst", "Beta Inc", "remote"),
        ("job-3", "DevOps Engineer", "Gamma Ltd", "bandung"),
    ]
    for key, title, company, location in jobs:
        await db_session.execute(
            text(
                "INSERT INTO jobs (id, title, company, location, is_active) "
                "VALUES (:id, :title, :company, :location, true) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": job_ids[key], "title": title, "company": company, "location": location},
        )

    links = [
        ("job-1", "Python"),
        ("job-1", "SQL"),
        ("job-2", "Python"),
        ("job-2", "SQL"),
        ("job-3", "Docker"),
        ("job-3", "Python"),
    ]
    for job_key, skill_name in links:
        await db_session.execute(
            text(
                "INSERT INTO job_required_skills (job_id, skill_id, is_required) "
                "VALUES (:job_id, :skill_id, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"job_id": job_ids[job_key], "skill_id": skill_ids[skill_name]},
        )
    await db_session.commit()


async def test_market_demand_computation_from_jobs(client, db_session) -> None:
    """Market demand should reflect skill frequency in active job postings."""
    await _insert_job_with_skills(db_session)
    reg = await _register(client)
    response = await client.get(
        "/api/market-demand",
        headers=_auth_header(reg["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_skills"] == 3
    skills = {s["skill"]: s for s in data["skills"]}
    assert "Python" in skills
    assert "SQL" in skills
    assert "Docker" in skills
    assert skills["Python"]["demand"] >= skills["SQL"]["demand"]
    assert skills["SQL"]["demand"] >= skills["Docker"]["demand"]


async def test_market_demand_job_count_does_not_inflate_with_skill_count(
    client, db_session: AsyncSession
) -> None:
    """job_count must reflect raw normalized frequency, not multiplied by total skills."""
    skill_ids = {}
    for name in ("Python", "SQL", "Docker"):
        result = await db_session.execute(
            text(
                "INSERT INTO skills (name, category, aliases) "
                "VALUES (:name, 'technical', ARRAY['x']) "
                "ON CONFLICT (name) DO UPDATE SET category = EXCLUDED.category "
                "RETURNING id"
            ),
            {"name": name},
        )
        skill_ids[name] = result.scalar_one()

    python_jobs = [str(uuid.uuid4()) for _ in range(5)]
    sql_jobs = [str(uuid.uuid4()) for _ in range(3)]
    docker_jobs = [str(uuid.uuid4()) for _ in range(2)]

    for jid in python_jobs + sql_jobs + docker_jobs:
        await db_session.execute(
            text(
                "INSERT INTO jobs (id, title, company, location, is_active) "
                "VALUES (:id, 'Engineer', 'Acme', 'ID', true) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": jid},
        )

    links = (
        [("Python", jid) for jid in python_jobs]
        + [("SQL", jid) for jid in sql_jobs]
        + [("Docker", jid) for jid in docker_jobs]
    )
    for skill, jid in links:
        await db_session.execute(
            text(
                "INSERT INTO job_required_skills (job_id, skill_id, is_required) "
                "VALUES (:job_id, :skill_id, true) "
                "ON CONFLICT DO NOTHING"
            ),
            {"job_id": jid, "skill_id": skill_ids[skill]},
        )
    await db_session.commit()

    reg = await _register(client)
    response = await client.get(
        "/api/market-demand",
        headers=_auth_header(reg["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    skill_map = {s["skill"]: s for s in data["skills"]}

    assert skill_map["Python"]["job_count"] == 5
    assert skill_map["SQL"]["job_count"] == 3
    assert skill_map["Docker"]["job_count"] == 2
    for entry in data["skills"]:
        assert entry["job_count"] <= 5


async def test_learning_path_includes_market_demand(client, db_session) -> None:
    """Learning path response should include market_demand field."""
    await _insert_job_with_skills(db_session)
    reg = await _register(client)
    response = await client.post(
        "/api/learning-path",
        headers=_auth_header(reg["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert "market_demand" in data
    assert isinstance(data["market_demand"], dict)
    assert "steps" in data
    assert "estimated_months" in data


async def test_market_demand_no_jobs_returns_empty(client) -> None:
    """When no jobs exist, market demand should be empty but endpoint works."""
    reg = await _register(client)
    response = await client.get(
        "/api/market-demand",
        headers=_auth_header(reg["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_skills"] == 0
    assert data["skills"] == []


async def test_market_demand_requires_auth(client) -> None:
    """Market demand endpoint without auth should return 401."""
    response = await client.get("/api/market-demand")
    assert response.status_code == 401
