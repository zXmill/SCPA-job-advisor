"""Durable model-feedback outbox tests."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import services.gateway.main as gateway_module


pytestmark = [pytest.mark.anyio, pytest.mark.db]


async def _register(client) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={
            "name": "Outbox User",
            "email": "outbox@example.com",
            "password": "Str0ng-Pass!word",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _insert_job(db_session: AsyncSession, job_id: str) -> None:
    await db_session.execute(
        text(
            "INSERT INTO jobs (id, title, company, posted_at, is_active) "
            "VALUES (:id, 'Backend Developer', 'SCPA Test', NOW(), true)"
        ),
        {"id": uuid.UUID(job_id)},
    )
    await db_session.commit()


async def test_feedback_pipeline_failure_is_durably_queued(
    client,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _register(client)
    job_id = str(uuid.uuid4())
    await _insert_job(db_session, job_id)

    async def fail_pipeline(_path: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise HTTPException(status_code=502, detail="pipeline unavailable")

    monkeypatch.setattr(gateway_module, "_pipeline_post", fail_pipeline)

    response = await client.post(
        "/api/recommendations/feedback",
        json={"job_id": job_id, "event": "click", "rank": 0, "dwell_ms": 2500},
        headers=_auth_header(user["access_token"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["pipeline"]["status"] == "queued"

    row = (
        await db_session.execute(
            text(
                "SELECT status, attempts, event_type, payload, last_error "
                "FROM model_feedback_outbox WHERE job_id = :job_id"
            ),
            {"job_id": uuid.UUID(job_id)},
        )
    ).mappings().one()
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    assert row["event_type"] == "click"
    assert row["payload"]["event"] == "click"
    assert row["payload"]["job_id"] == job_id
    assert "pipeline unavailable" in row["last_error"]


async def test_retry_model_feedback_outbox_once_marks_sent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "user_id": str(uuid.uuid4()),
        "job_id": str(uuid.uuid4()),
        "event": "save",
        "reward": 0.85,
    }
    outbox_id = (
        await db_session.execute(
            text(
                "INSERT INTO model_feedback_outbox "
                "(event_type, payload, status, attempts, next_attempt_at, created_at, updated_at) "
                "VALUES ('save', CAST(:payload AS jsonb), 'pending', 0, NOW(), NOW(), NOW()) "
                "RETURNING id"
            ),
            {"payload": json.dumps(payload)},
        )
    ).scalar_one()
    await db_session.commit()

    calls: list[tuple[str, dict[str, Any]]] = []

    async def send_feedback(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((path, payload))
        return {"status": "trained"}

    monkeypatch.setattr(gateway_module, "_pipeline_post", send_feedback)

    summary = await gateway_module.retry_model_feedback_outbox_once(db_session)

    assert summary == {"attempted": 1, "sent": 1, "failed": 0}
    assert calls == [("/feedback", payload)]
    row = (
        await db_session.execute(
            text(
                "SELECT status, attempts, delivered_at, last_error "
                "FROM model_feedback_outbox WHERE id = :id"
            ),
            {"id": outbox_id},
        )
    ).mappings().one()
    assert row["status"] == "sent"
    assert row["attempts"] == 1
    assert row["delivered_at"] is not None
    assert row["last_error"] is None
