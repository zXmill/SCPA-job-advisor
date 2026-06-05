"""Internal service-token boundary tests."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

import services.gateway.main as gateway_main
import services.pipeline.main as pipeline_main


@pytest.mark.anyio
async def test_pipeline_requires_internal_token_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_main, "INTERNAL_SERVICE_TOKEN", "unit-internal-token")

    transport = ASGITransport(app=pipeline_main.api)
    async with httpx.AsyncClient(transport=transport, base_url="http://pipeline") as client:
        response = await client.post(
            "/pipeline/run",
            json={"user_id": "u-1", "limit": 1},
        )
        wrong = await client.post(
            "/pipeline/run",
            json={"user_id": "u-1", "limit": 1},
            headers={pipeline_main.INTERNAL_SERVICE_TOKEN_HEADER: "wrong-token"},
        )
        allowed = await client.post(
            "/pipeline/run",
            json={"user_id": "u-1", "limit": 1},
            headers={pipeline_main.INTERNAL_SERVICE_TOKEN_HEADER: "unit-internal-token"},
        )

    assert response.status_code == 403
    assert wrong.status_code == 403
    assert allowed.status_code == 503


@pytest.mark.anyio
async def test_pipeline_health_stays_open_for_compose_healthcheck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_main, "INTERNAL_SERVICE_TOKEN", "unit-internal-token")

    transport = ASGITransport(app=pipeline_main.api)
    async with httpx.AsyncClient(transport=transport, base_url="http://pipeline") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_gateway_sends_internal_token_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"status": "ok"}

    class FakeClient:
        async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(gateway_main, "INTERNAL_SERVICE_TOKEN", "unit-internal-token")
    monkeypatch.setattr(gateway_main, "http_client", FakeClient())

    result = await gateway_main._pipeline_post("/pipeline/run", {"user_id": "u-1"})

    assert result == {"status": "ok"}
    assert captured["headers"] == {
        gateway_main.INTERNAL_SERVICE_TOKEN_HEADER: "unit-internal-token"
    }
