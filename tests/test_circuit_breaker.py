"""STEP 3 — Circuit Breaker Behavior Tests.

Verifies that the hybrid service remains partially operational when
downstream services (NCF, SBERT) fail. Tests the CLOSED → OPEN →
HALF_OPEN → CLOSED state machine transitions.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.hybrid.main import CircuitBreaker


class TestCircuitBreakerStateMachine:
    """Verify the full CLOSED → OPEN → HALF_OPEN → CLOSED lifecycle."""

    def test_initial_state_is_closed(self) -> None:
        """Circuit breaker must start in CLOSED state.

        All requests should pass through on initialization.
        """
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, name="test")
        assert cb.state == "closed"
        assert cb.can_execute() is True
        assert cb.failure_count == 0

    def test_stays_closed_below_threshold(self) -> None:
        """Failures below threshold do not open the circuit.

        N-1 failures should keep the circuit closed.
        """
        cb = CircuitBreaker(failure_threshold=5, name="test")
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_opens_at_exact_threshold(self) -> None:
        """Circuit opens when failures reach exactly the threshold.

        At this point, can_execute() must return False.
        """
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_open_rejects_requests(self) -> None:
        """Open circuit must reject all requests immediately.

        This prevents cascading failures to downstream services.
        """
        cb = CircuitBreaker(failure_threshold=2, name="test")
        cb.record_failure()
        cb.record_failure()

        # Should be consistently rejecting
        for _ in range(10):
            assert cb.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self) -> None:
        """After recovery_timeout seconds, circuit transitions to HALF_OPEN.

        HALF_OPEN allows one probe request to test if the service recovered.
        """
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, name="test"
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        time.sleep(0.15)

        assert cb.can_execute() is True
        assert cb.state == "half_open"

    def test_half_open_success_closes_circuit(self) -> None:
        """Successful request in HALF_OPEN state closes the circuit.

        This is the recovery path: service is back, resume normal operation.
        """
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, name="test"
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # → half_open

        cb.record_success()

        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self) -> None:
        """Failed request in HALF_OPEN state re-opens the circuit.

        The probe request failed, service is still down.
        """
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, name="test"
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # → half_open

        cb.record_failure()

        assert cb.state == "open"

    def test_success_in_closed_resets_count(self) -> None:
        """Successful request in CLOSED state resets failure counter.

        Intermittent failures shouldn't accumulate across successful requests.
        """
        cb = CircuitBreaker(failure_threshold=3, name="test")
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_full_recovery_cycle(self) -> None:
        """Full cycle: CLOSED → OPEN → HALF_OPEN → CLOSED.

        Simulates a real outage-and-recovery scenario.
        """
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, name="lifecycle"
        )

        # Phase 1: Normal operation
        assert cb.state == "closed"
        cb.record_success()
        cb.record_success()

        # Phase 2: Service goes down
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Phase 3: Wait for recovery timeout
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == "half_open"

        # Phase 4: Service recovers
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0

        # Phase 5: Normal operation resumed
        assert cb.can_execute() is True


class TestCircuitBreakerHybridIntegration:
    """Verify hybrid service correctly reports circuit states."""

    @pytest.mark.anyio
    async def test_metrics_show_circuit_states(self) -> None:
        """The /metrics endpoint should report circuit breaker states.

        Both NCF and SBERT circuit states must be visible for monitoring.
        """
        from httpx import ASGITransport, AsyncClient
        from services.hybrid.main import app as hybrid_app

        transport = ASGITransport(app=hybrid_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/metrics")

        assert r.status_code == 200
        metrics = r.json()["metrics"]
        assert "ncf_circuit" in metrics
        assert "sbert_circuit" in metrics
        assert metrics["ncf_circuit"] in ("closed", "open", "half_open")
        assert metrics["sbert_circuit"] in ("closed", "open", "half_open")

    @pytest.mark.anyio
    async def test_hybrid_survives_both_services_down(self) -> None:
        """Hybrid must return 200 even when both NCF and SBERT are down.

        In test mode (no real services), both fail. The hybrid service
        should fall back to deterministic random scores.
        """
        from httpx import ASGITransport, AsyncClient
        from services.hybrid.main import app as hybrid_app

        transport = ASGITransport(app=hybrid_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/recommend/hybrid", json={
                "user_id": "both-down-test",
                "user_profile_text": "Test profile",
                "is_new_user": False,
                "job_candidates": [
                    {"id": "j1", "desc": "Job 1"},
                    {"id": "j2", "desc": "Job 2"},
                ],
            })

        assert r.status_code == 200, (
            f"Hybrid should survive both services down, got {r.status_code}"
        )
        data = r.json()
        assert len(data["recommendations"]) == 2
