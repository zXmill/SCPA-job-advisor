"""Regression coverage for recommendation feedback slate persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import services.gateway.main as gateway_main


pytestmark = [pytest.mark.anyio, pytest.mark.db]


DEFAULT_PASSWORD = "Str0ng-Pass!word"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={
            "name": "Feedback Slate User",
            "email": "feedback-slate@example.com",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_feedback_after_recommendations_uses_persisted_served_slate(
    client,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = str(uuid.uuid4())
    pipeline_run_id = "feedback-slate-run"

    async def fake_pipeline_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path == "/pipeline/run":
            return {
                "run_id": pipeline_run_id,
                "ranked": [
                    {
                        "id": job_id,
                        "title": "Backend Recommendation Engineer",
                        "company": "SCPA Labs",
                        "location": "Jakarta, Indonesia",
                        "description": "Build feedback-aware recommendation systems.",
                        "posted_at": datetime.now(),
                        "source": "linkedin",
                        "final_score": 0.84,
                        "sbert_score": 0.9,
                        "ncf_score": 0.7,
                        "dqn_score": 0.6,
                        "match_percent": 84,
                        "model_provenance": {
                            "sbert": {"model_version": "unit-sbert"},
                            "ncf": {"model_version": "unit-ncf"},
                            "dqn": {"model_version": "unit-dqn"},
                        },
                    }
                ],
                "stages": {"aggregate": {"strategy": "unit"}},
            }
        if path == "/feedback":
            return {"status": "trained"}
        raise AssertionError(path)

    monkeypatch.setattr(gateway_main, "_pipeline_post", fake_pipeline_post)
    registration = await _register(client)
    headers = _auth_header(registration["access_token"])

    recommendation_response = await client.post(
        "/api/recommendations",
        headers=headers,
        json={"profile": {"location": "Jakarta", "skills": ["Python"]}},
    )
    assert recommendation_response.status_code == 200, recommendation_response.text
    recommendation = recommendation_response.json()["recommendations"][0]
    slate_id = recommendation["recommendation_id"]

    slate_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM served_slates WHERE id = :slate_id"),
            {"slate_id": uuid.UUID(slate_id)},
        )
    ).scalar_one()
    assert slate_count == 1

    feedback_response = await client.post(
        "/api/recommendations/feedback",
        headers=headers,
        json={
            "job_id": recommendation["job"]["id"],
            "recommendation_id": slate_id,
            "served_slate_id": slate_id,
            "event": "impression",
            "rank": 0,
            "slate_job_ids": [recommendation["job"]["id"]],
        },
    )
    assert feedback_response.status_code == 200, feedback_response.text

    feedback_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM feedback_events WHERE slate_id = :slate_id"),
            {"slate_id": uuid.UUID(slate_id)},
        )
    ).scalar_one()
    assert feedback_count == 1
