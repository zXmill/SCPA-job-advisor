"""Backend contracts for recommendation reason-filter scores."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import pytest

import services.gateway.main as gateway_main


pytestmark = [pytest.mark.anyio, pytest.mark.db]


DEFAULT_PASSWORD = "Str0ng-Pass!word"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={
            "name": "Reason Filter User",
            "email": "reason-filter@example.com",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_recommendations_include_reason_filter_scores(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = str(uuid.uuid4())
    posted_at = datetime.now()

    async def fake_pipeline_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert path == "/pipeline/run"
        assert payload["profile"]["location"] == "Jakarta"
        return {
            "run_id": "reason-run-1",
            "ranked": [
                {
                    "id": job_id,
                    "title": "Machine Learning Engineer",
                    "company": "SCPA Labs",
                    "location": "Jakarta, Indonesia",
                    "description": "Build recommendation systems with Python.",
                    "posted_at": posted_at,
                    "source": "linkedin",
                    "final_score": 0.81,
                    "sbert_score": 0.91,
                    "ncf_score": 0.73,
                    "dqn_score": 0.66,
                    "match_percent": 81,
                    "explanation": ["Strong semantic and interaction match."],
                }
            ],
            "stages": {"aggregate": {"strategy": "unit"}},
        }

    monkeypatch.setattr(gateway_main, "_pipeline_post", fake_pipeline_post)
    registration = await _register(client)

    response = await client.post(
        "/api/recommendations",
        json={"profile": {"location": "Jakarta", "skills": ["Python"]}},
        headers=_auth_header(registration["access_token"]),
    )

    assert response.status_code == 200, response.text
    recommendation = response.json()["recommendations"][0]
    assert recommendation["reason_filter_scores"] == {
        "semantic_fit": 0.91,
        "interaction_fit": 0.73,
        "session_rerank_signal": 0.66,
        "location_fit": 1.0,
        "recency": 1.0,
    }
    assert recommendation["reason_filter_labels"] == {
        "semantic_fit": "Highest SBERT semantic match",
        "interaction_fit": "Highest NCF interaction fit",
        "session_rerank_signal": "Highest DQN session rerank signal",
        "location_fit": "Closest profile location",
        "recency": "Newest jobs",
    }
