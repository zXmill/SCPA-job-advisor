"""Auth boundary tests for direct gateway pipeline execution."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

import services.gateway.main as gateway_main


@pytest.mark.anyio
async def test_direct_pipeline_run_is_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_pipeline_post(path: str, payload: dict[str, object]) -> dict[str, str]:
        calls.append((path, payload))
        return {"status": "ok"}

    monkeypatch.setattr(gateway_main, "_pipeline_post", fake_pipeline_post)

    user_token = gateway_main._create_access_token("user-1", role="user")
    admin_token = gateway_main._create_access_token("admin-1", role="admin")
    transport = ASGITransport(app=gateway_main.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        missing = await client.post("/pipeline/run", json={"user_id": "user-1"})
        user = await client.post(
            "/pipeline/run",
            json={"user_id": "user-1"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        admin = await client.post(
            "/pipeline/run",
            json={"user_id": "admin-1"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert missing.status_code == 401
    assert user.status_code == 403
    assert admin.status_code == 200
    assert admin.json() == {"status": "ok"}
    assert len(calls) == 1
    assert calls[0][0] == "/pipeline/run"
    assert calls[0][1]["user_id"] == "admin-1"
