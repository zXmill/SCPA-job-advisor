"""A/B testing and monitoring endpoint tests.

Covers:
    - POST /api/experiments          (create, validation, admin gate)
    - GET  /api/experiments          (list, filter by status)
    - GET  /api/experiments/{id}     (get detail)
    - POST /api/experiments/{id}/start   (start experiment)
    - POST /api/experiments/{id}/pause   (pause experiment)
    - POST /api/experiments/{id}/complete (complete experiment)
    - POST /api/experiments/{id}/assign  (assign user to variant)
    - GET  /api/experiments/{id}/metrics (aggregate metrics)
    - POST /api/events/track         (track conversion events)
    - Deterministic assignment hash   (same user -> same variant)
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import services.gateway.main as gateway_module


pytestmark = [pytest.mark.anyio, pytest.mark.db]

DEFAULT_PASSWORD = "Str0ng-Pass!word"


async def _register(client, *, name: str = "Test User",
                    email: str = "test@example.com",
                    password: str = DEFAULT_PASSWORD,
                    role: str = "user") -> dict[str, Any]:
    resp = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    if role == "admin":
        # Update role to admin for testing admin-only endpoints
        async with gateway_module.SessionLocal() as session:
            await session.execute(
                text("UPDATE users SET role = 'admin' WHERE id = :uid"),
                {"uid": data["user"]["id"]},
            )
            await session.commit()
    return data


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestCreateExperiment:
    async def test_create_experiment_requires_admin(self, client, db_session: AsyncSession) -> None:
        user = await _register(client, email="user1@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "reco-v2-test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 403

    async def test_create_experiment_success(self, client, db_session: AsyncSession) -> None:
        user = await _register(client, email="admin1@example.com", role="admin")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "reco-v2-test",
                "description": "Test new recommendation scoring",
                "variants": [
                    {"name": "control", "weight": 50, "config": {"dqn_weight": 0.3}},
                    {"name": "treatment", "weight": 50, "config": {"dqn_weight": 0.7}},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "reco-v2-test"
        assert data["status"] == "draft"
        assert data["target_metric"] == "click_through_rate"

    async def test_create_experiment_validation_fails_with_single_variant(self, client, db_session: AsyncSession) -> None:
        user = await _register(client, email="admin2@example.com", role="admin")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "bad-experiment",
                "variants": [
                    {"name": "only", "weight": 100},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 422


class TestListAndGetExperiment:
    async def test_list_experiments(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin3@example.com", role="admin")
        user = await _register(client, email="user2@example.com")
        for i in range(3):
            resp = await client.post(
                "/api/experiments",
                json={
                    "name": f"exp-{i}",
                    "variants": [
                        {"name": "control", "weight": 50},
                        {"name": "treatment", "weight": 50},
                    ],
                    "target_metric": "click_through_rate",
                },
                headers=_auth_header(admin["access_token"]),
            )
            assert resp.status_code == 200

        resp = await client.get("/api/experiments", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["experiments"]) == 3

    async def test_list_experiments_filter_by_status(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin4@example.com", role="admin")
        user = await _register(client, email="user3@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "draft-exp",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        assert resp.status_code == 200
        exp_id = resp.json()["id"]

        # Start it
        await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))

        resp = await client.get("/api/experiments?status=running", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["experiments"][0]["status"] == "running"

    async def test_get_experiment_by_id(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin5@example.com", role="admin")
        user = await _register(client, email="user4@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "get-test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "apply_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]
        resp = await client.get(f"/api/experiments/{exp_id}", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == exp_id
        assert data["name"] == "get-test"

    async def test_get_experiment_not_found(self, client, db_session: AsyncSession) -> None:
        user = await _register(client, email="user5@example.com")
        resp = await client.get("/api/experiments/00000000-0000-0000-0000-000000000000", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 404


class TestExperimentLifecycle:
    async def test_start_pause_complete_experiment(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin6@example.com", role="admin")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "lifecycle-test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]

        resp = await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        resp = await client.post(f"/api/experiments/{exp_id}/pause", headers=_auth_header(admin["access_token"]))
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

        resp = await client.post(f"/api/experiments/{exp_id}/complete", headers=_auth_header(admin["access_token"]))
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


class TestExperimentAssignment:
    async def test_assignment_is_deterministic(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin7@example.com", role="admin")
        user = await _register(client, email="user6@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "assign-test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]
        await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))

        resp = await client.post(f"/api/experiments/{exp_id}/assign", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        first_variant = resp.json()["variant_name"]

        # Same user should get the same variant
        resp = await client.post(f"/api/experiments/{exp_id}/assign", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        assert resp.json()["variant_name"] == first_variant

    async def test_assignment_fails_for_not_running_experiment(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin8@example.com", role="admin")
        user = await _register(client, email="user7@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "not-running",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]

        resp = await client.post(f"/api/experiments/{exp_id}/assign", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 404


class TestExperimentMetrics:
    async def test_metrics_empty_experiment(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin9@example.com", role="admin")
        user = await _register(client, email="user8@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "metrics-empty",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]
        await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))

        resp = await client.get(f"/api/experiments/{exp_id}/metrics", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment_id"] == exp_id
        # No assignments yet, so metrics may be empty
        assert "metrics" in data

    async def test_metrics_with_events(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin10@example.com", role="admin")
        user = await _register(client, email="user9@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "metrics-with-events",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]
        await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))

        # Assign user
        resp = await client.post(f"/api/experiments/{exp_id}/assign", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        variant = resp.json()["variant_name"]

        # Track events (no job_id to avoid FK constraint in tests)
        resp = await client.post(
            "/api/events/track",
            json={
                "experiment_id": exp_id,
                "event_type": "impression",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 200

        resp = await client.post(
            "/api/events/track",
            json={
                "experiment_id": exp_id,
                "event_type": "click",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 200

        # Check metrics
        resp = await client.get(f"/api/experiments/{exp_id}/metrics", headers=_auth_header(user["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert variant in data["metrics"]
        assert data["metrics"][variant]["impressions"] == 1
        assert data["metrics"][variant]["clicks"] == 1
        assert data["metrics"][variant]["ctr_proxy"] == 1.0


class TestTrackEvent:
    async def test_track_event_requires_assignment(self, client, db_session: AsyncSession) -> None:
        admin = await _register(client, email="admin11@example.com", role="admin")
        user = await _register(client, email="user10@example.com")
        resp = await client.post(
            "/api/experiments",
            json={
                "name": "track-test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
            headers=_auth_header(admin["access_token"]),
        )
        exp_id = resp.json()["id"]
        await client.post(f"/api/experiments/{exp_id}/start", headers=_auth_header(admin["access_token"]))

        resp = await client.post(
            "/api/events/track",
            json={
                "experiment_id": exp_id,
                "event_type": "click",
            },
            headers=_auth_header(user["access_token"]),
        )
        assert resp.status_code == 400
        assert "not assigned" in resp.json()["detail"].lower()
