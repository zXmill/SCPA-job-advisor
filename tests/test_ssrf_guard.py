"""SSRF guard tests for scraper URL fetches."""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

import services.scraper.main as scraper_main


def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scraper_main,
        "_resolve_host_addresses",
        lambda _host: ["93.184.216.34"],
    )


def test_scrape_url_allows_approved_job_board_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch)

    validated = scraper_main._validate_scrape_url("https://id.jobstreet.com/id/jobs")

    assert validated == "https://id.jobstreet.com/id/jobs"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/admin",
        "http://127.0.0.1:8000/admin",
        "http://[::1]:8000/admin",
        "http://169.254.169.254/latest/meta-data",
        "ftp://id.jobstreet.com/jobs",
        "https://example.com/jobs",
    ],
)
def test_scrape_url_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(HTTPException) as exc:
        scraper_main._validate_scrape_url(url)

    assert exc.value.status_code == 400


def test_scrape_url_rejects_dns_rebinding_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scraper_main,
        "_resolve_host_addresses",
        lambda _host: ["10.10.0.5"],
    )

    with pytest.raises(HTTPException) as exc:
        scraper_main._validate_scrape_url("https://id.jobstreet.com/id/jobs")

    assert exc.value.status_code == 400
    assert "private" in str(exc.value.detail).lower()


@pytest.mark.anyio
async def test_scrape_url_rejects_redirect_to_unsafe_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _public_dns(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "id.jobstreet.com"
        return httpx.Response(
            status_code=302,
            headers={"location": "http://127.0.0.1/admin"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HTTPException) as exc:
            await scraper_main._fetch_safe_url(
                client,
                "https://id.jobstreet.com/id/jobs",
            )

    assert exc.value.status_code == 400
