"""Tests for the link-status checker (Phase 1, deferred action #5).

Offline coverage: pure classifier + grace-window state machine + JSON-LD signal
extraction, plus SSRF / redirect / 429 behavior driven through
``httpx.MockTransport`` with an injected fake DNS resolver (no network). One
``db``-marked test proves the worker updates the ``link_status`` columns and
never touches ``is_active``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import text

from services.pipeline import link_status_checker as lsc


NOW = datetime(2026, 7, 2, tzinfo=timezone.utc)


async def _fake_resolver(host: str) -> list[str]:
    """Resolve every host to a public IP so SSRF logic runs offline."""
    return ["93.184.216.34"]


def _checker(**cfg) -> lsc.LinkStatusChecker:
    config = lsc.LinkCheckConfig(report_dir=None, request_delay_seconds=0.0, **cfg)
    return lsc.LinkStatusChecker(config=config, resolver_async=_fake_resolver)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── classify_signal (pure) ───────────────────────────────────────────────────

def test_classify_200_alive() -> None:
    assert lsc.classify_signal(200, lsc.JobPostingSignals(), NOW) == lsc.SIGNAL_ALIVE


@pytest.mark.parametrize("status", [404, 410])
def test_classify_gone_is_closed(status: int) -> None:
    assert lsc.classify_signal(status, lsc.JobPostingSignals(), NOW) == lsc.STATUS_CLOSED


@pytest.mark.parametrize("status", [401, 403, 500, 502, 503])
def test_classify_errors_are_unreachable(status: int) -> None:
    assert lsc.classify_signal(status, lsc.JobPostingSignals(), NOW) == lsc.STATUS_UNREACHABLE


def test_classify_expired_validthrough() -> None:
    sig = lsc.JobPostingSignals(valid_through=NOW - timedelta(days=1))
    assert lsc.classify_signal(200, sig, NOW) == lsc.STATUS_EXPIRED


def test_classify_future_validthrough_alive() -> None:
    sig = lsc.JobPostingSignals(valid_through=NOW + timedelta(days=30))
    assert lsc.classify_signal(200, sig, NOW) == lsc.SIGNAL_ALIVE


def test_classify_closed_marker() -> None:
    sig = lsc.JobPostingSignals(closed_marker=True)
    assert lsc.classify_signal(200, sig, NOW) == lsc.STATUS_CLOSED


# ── extract_posting_signals (pure) ───────────────────────────────────────────

def test_extract_validthrough_from_ld_json() -> None:
    html = (
        '<html><script type="application/ld+json">'
        '{"@type":"JobPosting","validThrough":"2020-01-01T00:00:00Z"}'
        "</script></html>"
    )
    sig = lsc.extract_posting_signals(html, now=NOW)
    assert sig.valid_through is not None and sig.valid_through.year == 2020


def test_extract_validthrough_from_graph_and_date_only() -> None:
    html = (
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"JobPosting","validThrough":"2019-05-06"}]}'
        "</script>"
    )
    sig = lsc.extract_posting_signals(html, now=NOW)
    assert sig.valid_through is not None and sig.valid_through.year == 2019


def test_extract_closed_marker_bilingual() -> None:
    assert lsc.extract_posting_signals("... No Longer Accepting Applications ...").closed_marker
    assert lsc.extract_posting_signals("Lowongan ini telah ditutup").closed_marker


def test_extract_no_signals() -> None:
    sig = lsc.extract_posting_signals("<html>hiring now</html>", now=NOW)
    assert sig.valid_through is None and sig.closed_marker is False


# ── apply_grace (pure state machine) ─────────────────────────────────────────

def test_grace_alive_resets() -> None:
    assert lsc.apply_grace(lsc.STATUS_CLOSED, 5, lsc.SIGNAL_ALIVE, 3) == (lsc.STATUS_OPEN, 0)


def test_grace_below_threshold_keeps_open() -> None:
    assert lsc.apply_grace(lsc.STATUS_OPEN, 0, lsc.STATUS_CLOSED, 3) == (lsc.STATUS_OPEN, 1)
    assert lsc.apply_grace(lsc.STATUS_OPEN, 1, lsc.STATUS_CLOSED, 3) == (lsc.STATUS_OPEN, 2)


def test_grace_flips_at_threshold() -> None:
    assert lsc.apply_grace(lsc.STATUS_OPEN, 2, lsc.STATUS_CLOSED, 3) == (lsc.STATUS_CLOSED, 3)


def test_grace_expired_flip() -> None:
    assert lsc.apply_grace(lsc.STATUS_OPEN, 2, lsc.STATUS_EXPIRED, 3) == (lsc.STATUS_EXPIRED, 3)


# ── check_one: SSRF / redirect / status handling (async, no network) ─────────

@pytest.mark.anyio
async def test_check_one_private_ip_never_fetched() -> None:
    called = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "http://169.254.169.254/latest/meta-data")
    assert outcome.signal == lsc.SIGNAL_SKIP
    assert called["n"] == 0  # SSRF guard blocks BEFORE any fetch


@pytest.mark.anyio
async def test_check_one_non_allowlisted_host_never_fetched() -> None:
    called = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200)

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://evil.example.com/job/1")
    assert outcome.signal == lsc.SIGNAL_SKIP
    assert called["n"] == 0


@pytest.mark.anyio
async def test_check_one_cross_host_redirect_blocked() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example.com/gotcha"})

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.SIGNAL_SKIP  # redirect off the allowlist is refused


@pytest.mark.anyio
async def test_check_one_redirect_to_expired_page_is_closed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/job/1":
            return httpx.Response(
                301, headers={"location": "https://www.kalibrr.com/job/1/expired"}
            )
        return httpx.Response(
            200,
            text="This job is No Longer Accepting Applications.",
            headers={"content-type": "text/html"},
        )

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.STATUS_CLOSED


@pytest.mark.anyio
async def test_check_one_404_is_closed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.STATUS_CLOSED
    assert outcome.http_status == 404


@pytest.mark.anyio
async def test_check_one_429_backoff_no_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.SIGNAL_BACKOFF


@pytest.mark.anyio
async def test_check_one_200_alive() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html>Apply now</html>", headers={"content-type": "text/html"}
        )

    checker = _checker()
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.SIGNAL_ALIVE


@pytest.mark.anyio
async def test_check_one_giant_body_truncated_not_oom() -> None:
    """R1: the response body is capped; a huge page cannot exhaust memory."""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="x" * 100_000, headers={"content-type": "text/html"}
        )

    checker = _checker(max_response_bytes=4096)
    async with _client(handler) as client:
        response = await lsc.url_safety.fetch_safe(
            client,
            "https://www.kalibrr.com/job/1",
            max_response_bytes=checker.config.max_response_bytes,
            resolver_async=_fake_resolver,
        )
    assert len(response.content) == 4096  # truncated at the cap, not 100k


@pytest.mark.anyio
async def test_check_one_marker_survives_truncation() -> None:
    """Closed markers within the cap still classify after truncation."""
    async def handler(request: httpx.Request) -> httpx.Response:
        body = "This job is no longer accepting applications." + ("pad " * 50_000)
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    checker = _checker(max_response_bytes=4096)
    async with _client(handler) as client:
        outcome = await checker.check_one(client, "https://www.kalibrr.com/job/1")
    assert outcome.signal == lsc.STATUS_CLOSED


# ── db: worker updates link_status columns, never is_active (INV-1) ──────────

@pytest.mark.anyio
@pytest.mark.db
async def test_worker_updates_link_status_and_leaves_is_active(db_engine, monkeypatch) -> None:
    job_id = uuid.uuid4()
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO jobs (id, title, company, source_url, is_active, link_status) "
                "VALUES (CAST(:id AS uuid), 'Engineer', 'Acme', "
                "'https://www.kalibrr.com/job/x', true, 'open')"
            ),
            {"id": str(job_id)},
        )

    checker = lsc.LinkStatusChecker(
        config=lsc.LinkCheckConfig(
            report_dir=None, grace_failures=1, test_max_cycles=1, request_delay_seconds=0.0
        ),
        engine=db_engine,
        resolver_async=_fake_resolver,
    )

    async def fake_check_one(client, source_url):
        return lsc.CheckOutcome(signal=lsc.STATUS_CLOSED, http_status=404)

    monkeypatch.setattr(checker, "check_one", fake_check_one)
    await checker.run()

    async with db_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT link_status, consecutive_check_failures, last_http_status, "
                    "is_active FROM jobs WHERE id = CAST(:id AS uuid)"
                ),
                {"id": str(job_id)},
            )
        ).mappings().one()

    assert row["link_status"] == "closed"
    assert row["consecutive_check_failures"] == 1
    assert row["last_http_status"] == 404
    assert row["is_active"] is True  # INV-1: checker never writes is_active
