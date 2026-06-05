"""Backend contracts for the admin model-health dashboard."""

from __future__ import annotations

from typing import Any

import pytest

import services.gateway.main as gateway_main


pytestmark = [pytest.mark.anyio]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pipeline_health_payload() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "pipeline",
        "mode": "http-orchestration-only",
        "p95_target_ms": 150,
        "downstream": {
            "scraper": "http://scraper:8001",
            "sbert": "http://sbert:8002",
            "ncf": "http://ncf:8003",
            "dqn": "http://dqn:8004",
        },
        "continual_training": {
            "enabled": True,
            "interval_seconds": 3600,
            "cycles": 4,
            "last_error": None,
            "scrape_target": 2000,
            "candidate_pool_limit": 250,
        },
        "telemetry": {
            "window_size": 200,
            "p95_target_ms": 150,
            "stages": {
                "scrape": {"count": 2, "last_ms": 11.0, "p50_ms": 10.0, "p95_ms": 12.0},
                "sbert": {"count": 2, "last_ms": 21.0, "p50_ms": 20.0, "p95_ms": 22.0},
                "ncf": {"count": 2, "last_ms": 8.0, "p50_ms": 7.0, "p95_ms": 9.0},
                "dqn": {"count": 2, "last_ms": 6.0, "p50_ms": 5.0, "p95_ms": 7.0},
                "calibrator": {"count": 2, "last_ms": 1.0, "p50_ms": 1.0, "p95_ms": 1.0},
                "aggregation": {"count": 2, "last_ms": 2.0, "p50_ms": 2.0, "p95_ms": 3.0},
            },
        },
    }


async def test_admin_model_health_requires_admin_role(client) -> None:
    user_token = gateway_main._create_access_token("user-1", role="user")

    missing = await client.get("/api/admin/model-health")
    forbidden = await client.get(
        "/api/admin/model-health",
        headers=_auth_header(user_token),
    )

    assert missing.status_code == 401
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Admin role required"


async def test_admin_model_health_returns_pipeline_model_summary(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float | None]] = []

    async def fake_pipeline_get(path: str, timeout: float | None = None) -> dict[str, Any]:
        calls.append((path, timeout))
        return _pipeline_health_payload()

    monkeypatch.setattr(gateway_main, "_pipeline_get", fake_pipeline_get)
    admin_token = gateway_main._create_access_token("admin-1", role="admin")

    response = await client.get(
        "/api/admin/model-health",
        headers=_auth_header(admin_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "healthy"
    assert body["pipeline"] == {
        "status": "healthy",
        "mode": "http-orchestration-only",
        "p95_target_ms": 150,
    }
    assert body["models"]["sbert"] == {
        "status": "configured",
        "url": "http://sbert:8002",
        "stage": body["telemetry"]["stages"]["sbert"],
    }
    assert body["models"]["ncf"]["url"] == "http://ncf:8003"
    assert body["models"]["dqn"]["url"] == "http://dqn:8004"
    assert body["models"]["calibrator"] == {
        "status": "active",
        "stage": body["telemetry"]["stages"]["calibrator"],
    }
    assert body["continual_training"]["cycles"] == 4
    assert calls == [("/health", gateway_main.HEALTH_TIMEOUT_SECONDS)]
