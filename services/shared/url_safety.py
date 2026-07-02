"""Shared SSRF guard for outbound job-board fetches.

Extracted from ``services.scraper.main`` so non-FastAPI callers (e.g. the
pipeline link-status checker, whose image does not ship ``services/scraper``)
can reuse the exact same allowlist + private-IP defense without importing a
FastAPI app.

Design notes:
    - Errors are plain exceptions, NOT ``fastapi.HTTPException``. Callers that
      are HTTP routes wrap :class:`UnsafeUrlError` / :class:`HostResolutionError`
      into their own 4xx.
    - :class:`UnsafeUrlError` deliberately subclasses :class:`Exception` (not
      ``ValueError``): the validation flow probes ``ipaddress.ip_address`` and
      catches ``ValueError`` to detect non-literal hostnames, so an
      ``UnsafeUrlError`` that subclassed ``ValueError`` could be swallowed.
    - DNS resolution is injectable so callers keep a monkeypatch seam for tests.
    - ``UnsafeUrlError`` (scheme / host-not-allowed / resolves-private) means
      *do not fetch*; ``HostResolutionError`` (DNS failure/timeout) is a distinct
      transient signal a caller may classify as "unreachable".
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from typing import Awaitable
from urllib.parse import urljoin, urlparse

import httpx


class UnsafeUrlError(Exception):
    """A URL failed the SSRF guard (bad scheme, host, or private target)."""


class HostResolutionError(Exception):
    """A hostname could not be resolved (transient / DNS failure)."""


ALLOWED_SCHEMES = frozenset({"http", "https"})

# Public job-board host suffixes the platform is permitted to fetch. Kept in
# sync with the scraper's seed domains; a URL must match one of these AND
# resolve to a public IP.
DEFAULT_ALLOWED_HOST_SUFFIXES = frozenset(
    {
        "linkedin.com",
        "indeed.com",
        "kalibrr.com",
        "karir.com",
        "jobstreet.com",
        "jobstreet.co.id",
        "glints.com",
        "techinasia.com",
        "remotive.com",
        "topkarir.com",
        "kitalulus.com",
    }
)

# Redirect hops to follow before giving up; each hop is re-validated.
DEFAULT_MAX_REDIRECTS = 5
# Mirrors the scraper's _MAX_SOURCE_RESPONSE_BYTES cap (1.5 MB): the final
# response body is streamed and truncated at this size to bound memory.
DEFAULT_MAX_RESPONSE_BYTES = 1_500_000
DEFAULT_DNS_TIMEOUT_SECONDS = 2.0

SyncResolver = Callable[[str], list[str]]
AsyncResolver = Callable[[str], Awaitable[list[str]]]


def is_allowed_host(
    hostname: str,
    allowed_suffixes: frozenset[str] = DEFAULT_ALLOWED_HOST_SUFFIXES,
) -> bool:
    """True if ``hostname`` equals or is a subdomain of an allowed suffix."""
    host = hostname.rstrip(".").lower()
    return any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in allowed_suffixes
    )


def is_unsafe_address(address: str) -> bool:
    """True if ``address`` (an IP literal) is not globally routable.

    Raises ``ValueError`` if ``address`` is not a valid IP literal — callers
    use that to distinguish IP-literal hosts from regular hostnames.
    """
    ip = ipaddress.ip_address(address)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return not ip.is_global


def resolve_host_addresses(
    hostname: str, *, timeout: float | None = None
) -> list[str]:
    """Synchronously resolve ``hostname`` to a sorted list of IP strings."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HostResolutionError(
            f"host could not be resolved: {hostname}"
        ) from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise HostResolutionError(f"host could not be resolved: {hostname}")
    return addresses


async def resolve_host_addresses_async(
    hostname: str, *, timeout: float | None = DEFAULT_DNS_TIMEOUT_SECONDS
) -> list[str]:
    """Async DNS resolution with a timeout, off the event loop thread."""
    try:
        infos = await asyncio.wait_for(
            asyncio.to_thread(
                socket.getaddrinfo, hostname, None, type=socket.SOCK_STREAM
            ),
            timeout=timeout,
        )
    except (TimeoutError, asyncio.TimeoutError) as exc:
        raise HostResolutionError(f"host resolution timed out: {hostname}") from exc
    except socket.gaierror as exc:
        raise HostResolutionError(
            f"host could not be resolved: {hostname}"
        ) from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise HostResolutionError(f"host could not be resolved: {hostname}")
    return addresses


def _check_scheme_and_host(url: str) -> str:
    """Validate scheme + host shape; return the lowercased host or raise."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError("URL scheme is not allowed")
    if not parsed.hostname:
        raise UnsafeUrlError("URL host is required")
    host = parsed.hostname.rstrip(".").lower()

    # Raw IP-literal hosts are never on the allowlist, so reject them here. The
    # single expression in the ``try`` is ``is_unsafe_address`` (which raises
    # ValueError only for non-IP-literal hostnames); the ``raise`` statements sit
    # OUTSIDE the ``try`` so an UnsafeUrlError can never be swallowed. Preserves
    # the original detail wording: a private literal reports "private or
    # non-public", a public-but-unlisted literal reports "host is not allowed".
    try:
        unsafe = is_unsafe_address(host)
    except ValueError:
        return host  # not an IP literal → a normal hostname, continue
    if unsafe:
        raise UnsafeUrlError("URL resolves to private or non-public address")
    raise UnsafeUrlError("URL host is not allowed")


def validate_url(
    url: str,
    *,
    allowed_suffixes: frozenset[str] = DEFAULT_ALLOWED_HOST_SUFFIXES,
    resolver: SyncResolver = resolve_host_addresses,
    resolve_dns: bool = True,
) -> str:
    """Return ``url`` if it passes the SSRF guard, else raise.

    Raises :class:`UnsafeUrlError` for a bad scheme/host or a private-resolving
    target, and :class:`HostResolutionError` (from ``resolver``) on DNS failure.
    """
    host = _check_scheme_and_host(url)
    if not is_allowed_host(host, allowed_suffixes):
        raise UnsafeUrlError("URL host is not allowed")
    if resolve_dns:
        for address in resolver(host):
            if is_unsafe_address(address):
                raise UnsafeUrlError(
                    "URL resolves to private or non-public address"
                )
    return url


async def validate_url_async(
    url: str,
    *,
    allowed_suffixes: frozenset[str] = DEFAULT_ALLOWED_HOST_SUFFIXES,
    resolver_async: AsyncResolver = resolve_host_addresses_async,
) -> str:
    """Async variant of :func:`validate_url` (host-shape sync, DNS async)."""
    host = _check_scheme_and_host(url)
    if not is_allowed_host(host, allowed_suffixes):
        raise UnsafeUrlError("URL host is not allowed")
    for address in await resolver_async(host):
        if is_unsafe_address(address):
            raise UnsafeUrlError("URL resolves to private or non-public address")
    return url


async def fetch_safe(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float | None = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_response_bytes: int | None = DEFAULT_MAX_RESPONSE_BYTES,
    allowed_suffixes: frozenset[str] = DEFAULT_ALLOWED_HOST_SUFFIXES,
    resolver_async: AsyncResolver = resolve_host_addresses_async,
) -> httpx.Response:
    """GET ``url`` following redirects manually, re-validating every hop.

    ``follow_redirects`` is forced off; each ``Location`` is re-run through
    :func:`validate_url_async` before the next request, closing the redirect-to-
    internal-host SSRF hole. Raises :class:`UnsafeUrlError` /
    :class:`HostResolutionError` on any unsafe hop.

    The final response body is streamed and truncated at ``max_response_bytes``
    (an allowlisted-but-misbehaving endpoint must not be able to OOM the
    caller). Truncation is safe for liveness classification: closed markers and
    JSON-LD blocks live in the first part of a job page.
    """
    current_url = await validate_url_async(
        url, allowed_suffixes=allowed_suffixes, resolver_async=resolver_async
    )
    for _ in range(max_redirects + 1):
        request = client.build_request("GET", current_url, timeout=timeout)
        response = await client.send(request, stream=True, follow_redirects=False)
        if not response.is_redirect:
            try:
                if max_response_bytes is None:
                    await response.aread()
                else:
                    received = bytearray()
                    async for chunk in response.aiter_bytes():
                        remaining = max_response_bytes - len(received)
                        if remaining <= 0:
                            break
                        received.extend(chunk[:remaining])
                    response._content = bytes(received)  # capped body for .text/.content
            finally:
                await response.aclose()
            return response
        await response.aclose()
        location = response.headers.get("location")
        if not location:
            raise UnsafeUrlError("redirect is missing a location header")
        current_url = await validate_url_async(
            urljoin(str(response.url), location),
            allowed_suffixes=allowed_suffixes,
            resolver_async=resolver_async,
        )
    raise UnsafeUrlError("redirect limit exceeded")
