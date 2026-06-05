"""Backend contracts for durable job alerts."""

from __future__ import annotations

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
    email: str = "alerts-user@example.com",
    name: str = "Alerts User",
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _alert_row(db_session: AsyncSession, alert_id: int) -> dict[str, Any]:
    row = (
        await db_session.execute(
            text(
                "SELECT user_id, name, query, location, min_match_percent, "
                "frequency, active FROM job_alerts WHERE id = :alert_id"
            ),
            {"alert_id": alert_id},
        )
    ).mappings().one()
    return dict(row)


async def test_job_alerts_require_auth(client) -> None:
    response = await client.post(
        "/api/job-alerts",
        json={"name": "Backend alerts", "query": "backend"},
    )

    assert response.status_code == 401


async def test_user_can_create_and_list_only_their_job_alerts(
    client,
    db_session: AsyncSession,
) -> None:
    first_user = await _register(client, email="alerts-one@example.com")
    second_user = await _register(client, email="alerts-two@example.com")
    payload = {
        "name": "Backend Jakarta",
        "query": "backend developer",
        "location": "Jakarta",
        "min_match_percent": 70,
        "frequency": "daily",
    }

    create_response = await client.post(
        "/api/job-alerts",
        headers=_auth_header(first_user["access_token"]),
        json=payload,
    )
    first_list = await client.get(
        "/api/job-alerts",
        headers=_auth_header(first_user["access_token"]),
    )
    second_list = await client.get(
        "/api/job-alerts",
        headers=_auth_header(second_user["access_token"]),
    )

    assert create_response.status_code == 200, create_response.text
    body = create_response.json()
    assert body["name"] == "Backend Jakarta"
    assert body["query"] == "backend developer"
    assert body["location"] == "Jakarta"
    assert body["min_match_percent"] == 70
    assert body["frequency"] == "daily"
    assert body["active"] is True
    assert body["criteria"] == {
        "query": "backend developer",
        "location": "Jakarta",
        "min_match_percent": 70,
    }

    assert first_list.status_code == 200, first_list.text
    assert first_list.json()["total"] == 1
    assert first_list.json()["alerts"][0]["id"] == body["id"]
    assert second_list.status_code == 200, second_list.text
    assert second_list.json() == {"alerts": [], "total": 0}

    row = await _alert_row(db_session, body["id"])
    assert str(row["user_id"]) == first_user["user"]["id"]
    assert row["active"] is True


async def test_user_can_update_and_disable_own_job_alert(
    client,
    db_session: AsyncSession,
) -> None:
    user = await _register(client)
    headers = _auth_header(user["access_token"])
    create_response = await client.post(
        "/api/job-alerts",
        headers=headers,
        json={"name": "Data alerts", "query": "data", "location": "Jakarta"},
    )
    alert_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/job-alerts/{alert_id}",
        headers=headers,
        json={"location": "Bandung", "frequency": "weekly", "min_match_percent": 80},
    )
    disable_response = await client.delete(f"/api/job-alerts/{alert_id}", headers=headers)
    list_response = await client.get("/api/job-alerts", headers=headers)

    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["location"] == "Bandung"
    assert updated["frequency"] == "weekly"
    assert updated["min_match_percent"] == 80
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json() == {"status": "disabled", "alert_id": alert_id}
    assert list_response.json() == {"alerts": [], "total": 0}

    row = await _alert_row(db_session, alert_id)
    assert row["location"] == "Bandung"
    assert row["frequency"] == "weekly"
    assert row["active"] is False


async def test_user_cannot_mutate_another_users_job_alert(client) -> None:
    owner = await _register(client, email="alerts-owner@example.com")
    other = await _register(client, email="alerts-other@example.com")
    create_response = await client.post(
        "/api/job-alerts",
        headers=_auth_header(owner["access_token"]),
        json={"name": "Owner alert", "query": "python"},
    )
    alert_id = create_response.json()["id"]
    other_headers = _auth_header(other["access_token"])

    update_response = await client.put(
        f"/api/job-alerts/{alert_id}",
        headers=other_headers,
        json={"name": "Hijacked"},
    )
    delete_response = await client.delete(
        f"/api/job-alerts/{alert_id}",
        headers=other_headers,
    )

    assert update_response.status_code == 404
    assert delete_response.status_code == 404


async def test_job_alert_rejects_invalid_frequency(client) -> None:
    user = await _register(client)

    response = await client.post(
        "/api/job-alerts",
        headers=_auth_header(user["access_token"]),
        json={"name": "Invalid alert", "query": "python", "frequency": "hourly"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported job alert frequency"
