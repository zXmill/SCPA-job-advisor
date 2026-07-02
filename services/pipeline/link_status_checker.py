"""24h job link / application-status checker (deferred action #5, Phase 1).

A long-running (or bounded) worker that re-checks each active job's ``source_url``
and records liveness in the ``jobs.link_status`` family of columns. It is the SOLE
writer of those columns and NEVER writes ``is_active`` — so a re-scrape (whose
upsert sets ``is_active`` but not ``link_status``) can never resurrect a verdict.

Phase 1 is write-only: nothing here changes retrieval or listing SQL. A later
phase gates visibility on ``link_status``.

Safety: every outbound request goes through ``services.shared.url_safety`` (scheme
+ host-allowlist + resolved-IP guard, redirects re-validated per hop) — the DB
``source_url`` is treated as untrusted. Politeness: hosts are checked with a
bounded per-host concurrency and an inter-request delay; HTTP 429 backs off and
never counts as a failure.

Verdict model (per check → a raw signal), then a grace window:
    alive       200 and not expired/closed
    expired     JSON-LD JobPosting ``validThrough`` in the past
    closed      404 / 410, or a matched "no longer accepting" marker
    unreachable timeout / 5xx / other 4xx / DNS failure
Any non-``alive`` signal increments ``consecutive_check_failures``; only once it
reaches ``grace_failures`` does ``link_status`` flip off ``open``. Any ``alive``
resets the counter and sets ``open``.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import signal
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

try:  # Local harness runs can reuse the repo .env; containers already use env.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - pipeline image receives explicit env.
    pass

from services.shared import url_safety


logger = logging.getLogger("scpa.pipeline.link_status_checker")
DEFAULT_REPORT_DIR = Path("reports/debug/link_status")

# Bilingual (id/en) "no longer accepting applications" markers. Substring match
# on the fetched HTML. Seeded conservatively; tuned against real fixtures in P2.
CLOSED_MARKERS: tuple[str, ...] = (
    "no longer accepting applications",
    "no longer accepting application",
    "this job is no longer available",
    "this position has been filled",
    "position has been filled",
    "job has expired",
    "this posting has expired",
    "applications are closed",
    "lowongan ini sudah tidak tersedia",
    "lowongan sudah ditutup",
    "lowongan ini telah ditutup",
    "posisi ini sudah terisi",
    "tidak lagi menerima lamaran",
    "pendaftaran telah ditutup",
)

# link_status column values (String(16) in db.models.Job).
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_EXPIRED = "expired"
STATUS_UNREACHABLE = "unreachable"

# Raw per-check signals (pre grace window).
SIGNAL_ALIVE = "alive"
SIGNAL_SKIP = "skip"  # url failed the SSRF guard → never fetched, verdict unchanged
SIGNAL_BACKOFF = "backoff"  # HTTP 429 → rotate, never a failure
# The remaining raw signals reuse the terminal status names: closed/expired/unreachable.

_LD_JSON_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _database_url() -> str | None:
    raw = (
        os.getenv("PIPELINE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("GATEWAY_DATABASE_URL")
    )
    if not raw:
        return None
    if raw.startswith("postgresql+psycopg2://"):
        return raw.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


@dataclass(frozen=True)
class LinkCheckConfig:
    run_forever: bool = False
    check_interval_seconds: float = 86400.0
    # Jobs re-checked per cycle. For true ~24h coverage this should be >= the
    # active catalog size (each cycle takes the oldest-checked N); below that,
    # coverage is rolling over several days. Politeness is governed by the
    # per-host delay, not this cap, so a full-catalog batch is safe.
    batch_limit: int = 2000
    host_concurrency: int = 4
    request_delay_seconds: float = 1.0
    request_timeout_seconds: float = 15.0
    max_redirects: int = 5
    max_response_bytes: int = url_safety.DEFAULT_MAX_RESPONSE_BYTES
    grace_failures: int = 3
    unreachable_hide_failures: int = 7  # recorded for the Phase 2 gate; not enforced here
    test_max_cycles: int | None = 1
    report_dir: Path | None = DEFAULT_REPORT_DIR

    @classmethod
    def from_env(cls) -> "LinkCheckConfig":
        test_raw = os.getenv("LINK_CHECKER_TEST_MAX_CYCLES", "").strip()
        test_max_cycles = int(test_raw) if test_raw else None
        run_forever = _env_bool("LINK_CHECKER_RUN_FOREVER", False)
        if not run_forever and test_max_cycles is None:
            test_max_cycles = 1
        report_dir_raw = os.getenv("LINK_CHECKER_REPORT_DIR", str(DEFAULT_REPORT_DIR)).strip()
        return cls(
            run_forever=run_forever,
            check_interval_seconds=max(0.0, float(os.getenv("LINK_CHECKER_INTERVAL_SECONDS", "86400"))),
            batch_limit=max(1, int(os.getenv("LINK_CHECKER_BATCH_LIMIT", "2000"))),
            host_concurrency=max(1, int(os.getenv("LINK_CHECKER_HOST_CONCURRENCY", "4"))),
            request_delay_seconds=max(0.0, float(os.getenv("LINK_CHECKER_REQUEST_DELAY_SECONDS", "1"))),
            request_timeout_seconds=max(1.0, float(os.getenv("LINK_CHECKER_REQUEST_TIMEOUT_SECONDS", "15"))),
            max_redirects=max(0, int(os.getenv("LINK_CHECKER_MAX_REDIRECTS", "5"))),
            max_response_bytes=max(
                1024,
                int(
                    os.getenv(
                        "LINK_CHECKER_MAX_RESPONSE_BYTES",
                        str(url_safety.DEFAULT_MAX_RESPONSE_BYTES),
                    )
                ),
            ),
            grace_failures=max(1, int(os.getenv("LINK_CHECKER_GRACE_FAILURES", "3"))),
            unreachable_hide_failures=max(1, int(os.getenv("LINK_CHECKER_UNREACHABLE_HIDE_FAILURES", "7"))),
            test_max_cycles=test_max_cycles,
            report_dir=Path(report_dir_raw) if report_dir_raw else None,
        )


@dataclass(frozen=True)
class JobPostingSignals:
    valid_through: datetime | None = None
    closed_marker: bool = False


@dataclass(frozen=True)
class CheckOutcome:
    signal: str
    http_status: int | None = None


@dataclass(frozen=True)
class CycleSummary:
    cycle_number: int
    started_at: str
    finished_at: str
    checked: int
    counts: dict[str, int] = field(default_factory=dict)


# ── Pure helpers (unit-tested offline) ──────────────────────────────────────

def _parse_iso_datetime(raw: str) -> datetime | None:
    value = str(raw).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        # Date-only or unexpected shape: try the leading YYYY-MM-DD.
        try:
            parsed = datetime.fromisoformat(value[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iter_ld_json_objects(payload: object):
    """Yield candidate dict nodes from a parsed JSON-LD payload (incl. @graph)."""
    if isinstance(payload, list):
        for entry in payload:
            yield from _iter_ld_json_objects(entry)
    elif isinstance(payload, dict):
        yield payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for entry in graph:
                yield from _iter_ld_json_objects(entry)


def _is_job_posting(item: dict) -> bool:
    ld_type = item.get("@type") or ""
    if isinstance(ld_type, str):
        return "JobPosting" in ld_type
    if isinstance(ld_type, (list, tuple)):
        return any("JobPosting" in str(entry) for entry in ld_type)
    return False


def extract_posting_signals(html: str, *, now: datetime | None = None) -> JobPostingSignals:
    """Extract liveness signals from a job page: validThrough + closed markers."""
    if not html:
        return JobPostingSignals()
    lowered = html.lower()
    closed_marker = any(marker in lowered for marker in CLOSED_MARKERS)

    valid_through: datetime | None = None
    for block in _LD_JSON_RE.findall(html):
        try:
            payload = json.loads(block.strip() or "{}")
        except json.JSONDecodeError:
            continue
        for item in _iter_ld_json_objects(payload):
            if not _is_job_posting(item):
                continue
            candidate = _parse_iso_datetime(str(item.get("validThrough") or ""))
            if candidate is not None:
                valid_through = candidate
    return JobPostingSignals(valid_through=valid_through, closed_marker=closed_marker)


def classify_signal(http_status: int, signals: JobPostingSignals, now: datetime) -> str:
    """Map one HTTP check to a raw signal (before the grace window).

    Note: 429 is handled by the caller as a back-off and never reaches here.
    """
    if http_status in (404, 410):
        return STATUS_CLOSED
    if http_status >= 400:
        # 401/403/5xx/other errors → transient; never hide a job on an auth
        # block or a server hiccup.
        return STATUS_UNREACHABLE
    if signals.closed_marker:
        return STATUS_CLOSED
    if signals.valid_through is not None and signals.valid_through < now:
        return STATUS_EXPIRED
    return SIGNAL_ALIVE


def apply_grace(
    current_status: str,
    current_failures: int,
    raw_signal: str,
    grace_failures: int,
) -> tuple[str, int]:
    """Grace-window state machine. Pure.

    ``alive`` → (open, 0). Any dead signal increments the failure counter and only
    flips ``link_status`` once the counter reaches ``grace_failures``; below that
    the prior status is kept (transient outages don't hide live jobs).
    """
    if raw_signal == SIGNAL_ALIVE:
        return (STATUS_OPEN, 0)
    failures = current_failures + 1
    if failures >= grace_failures:
        return (raw_signal, failures)
    return (current_status, failures)


# ── Worker ──────────────────────────────────────────────────────────────────

_SELECT_BATCH_SQL = text(
    """
    SELECT id::text AS id, source_url, link_status, consecutive_check_failures
    FROM jobs
    WHERE is_active = true AND coalesce(source_url, '') <> ''
    ORDER BY last_checked_at ASC NULLS FIRST
    LIMIT :limit
    """
)

# NEVER writes is_active (INV-1): the checker owns only the link_status family.
_UPDATE_SQL = text(
    """
    UPDATE jobs
    SET link_status = :link_status,
        consecutive_check_failures = :failures,
        last_checked_at = NOW(),
        last_http_status = :http_status
    WHERE id = CAST(:id AS uuid)
    """
)

# Skip/backoff: rotate last_checked_at so the row moves to the back of the queue,
# but leave the verdict + failure counter untouched.
_ROTATE_SQL = text(
    """
    UPDATE jobs
    SET last_checked_at = NOW(), last_http_status = :http_status
    WHERE id = CAST(:id AS uuid)
    """
)


class LinkStatusChecker:
    def __init__(
        self,
        *,
        config: LinkCheckConfig,
        engine: AsyncEngine | None = None,
        resolver_async: url_safety.AsyncResolver | None = None,
    ) -> None:
        self.config = config
        self._engine = engine
        # Injectable DNS resolver seam: tests supply a fake so the SSRF/redirect
        # logic is exercised offline. Defaults to the real async resolver.
        self._resolver_async = resolver_async or url_safety.resolve_host_addresses_async
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            url = _database_url()
            if not url:
                raise RuntimeError(
                    "DATABASE_URL/PIPELINE_DATABASE_URL/GATEWAY_DATABASE_URL is required"
                )
            # Pool must cover host_concurrency writers (each host task opens
            # engine.begin() while others are in flight) or writes serialize on
            # the pool-acquire timeout when LINK_CHECKER_HOST_CONCURRENCY is raised.
            self._engine = create_async_engine(
                url,
                pool_pre_ping=True,
                pool_size=max(2, self.config.host_concurrency),
                max_overflow=self.config.host_concurrency,
            )
        return self._engine

    async def _load_batch(self) -> list[dict]:
        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(_SELECT_BATCH_SQL, {"limit": self.config.batch_limit})
            return [dict(row) for row in result.mappings().all()]

    async def check_one(self, client: httpx.AsyncClient, source_url: str) -> CheckOutcome:
        """Fetch one URL through the SSRF guard and classify it. No DB writes."""
        try:
            response = await url_safety.fetch_safe(
                client,
                source_url,
                timeout=self.config.request_timeout_seconds,
                max_redirects=self.config.max_redirects,
                max_response_bytes=self.config.max_response_bytes,
                resolver_async=self._resolver_async,
            )
        except url_safety.UnsafeUrlError as exc:
            logger.warning("link check skipped unsafe url=%s: %s", source_url, exc)
            return CheckOutcome(signal=SIGNAL_SKIP)
        except url_safety.HostResolutionError:
            return CheckOutcome(signal=STATUS_UNREACHABLE)
        except httpx.HTTPError:
            return CheckOutcome(signal=STATUS_UNREACHABLE)

        status = response.status_code
        if status == 429:
            return CheckOutcome(signal=SIGNAL_BACKOFF, http_status=status)
        body = response.text if status == 200 else ""
        raw = classify_signal(status, extract_posting_signals(body, now=_utcnow()), _utcnow())
        return CheckOutcome(signal=raw, http_status=status)

    async def _apply_outcome(self, conn, job: Mapping, outcome: CheckOutcome) -> str:
        if outcome.signal in (SIGNAL_SKIP, SIGNAL_BACKOFF):
            await conn.execute(_ROTATE_SQL, {"id": job["id"], "http_status": outcome.http_status})
            return outcome.signal
        new_status, new_failures = apply_grace(
            job["link_status"] or STATUS_OPEN,
            int(job["consecutive_check_failures"] or 0),
            outcome.signal,
            self.config.grace_failures,
        )
        await conn.execute(
            _UPDATE_SQL,
            {
                "id": job["id"],
                "link_status": new_status,
                "failures": new_failures,
                "http_status": outcome.http_status,
            },
        )
        return new_status

    async def _check_host_jobs(
        self, client: httpx.AsyncClient, jobs: Sequence[Mapping], counts: dict[str, int]
    ) -> None:
        engine = self._get_engine()
        for index, job in enumerate(jobs):
            if self._stop_event.is_set():
                return
            # Per-row isolation: one bad row / transient DB error must not abort
            # the host batch (or, via gather, cancel every other host).
            try:
                outcome = await self.check_one(client, job["source_url"])
                async with engine.begin() as conn:
                    resulting = await self._apply_outcome(conn, job, outcome)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("link check failed job=%s: %s", job["id"], exc)
                resulting = "error"
            counts[resulting] = counts.get(resulting, 0) + 1
            # Polite inter-request delay between same-host requests.
            if self.config.request_delay_seconds and index < len(jobs) - 1:
                await asyncio.sleep(self.config.request_delay_seconds)

    async def run_cycle(self, cycle_number: int) -> CycleSummary:
        started = _utcnow().isoformat()
        batch = await self._load_batch()
        counts: dict[str, int] = {}

        # Group by host so per-host serialization + delay throttles each board.
        by_host: dict[str, list[Mapping]] = {}
        for job in batch:
            host = (urlparse(job["source_url"]).hostname or "").lower()
            by_host.setdefault(host, []).append(job)

        semaphore = asyncio.Semaphore(self.config.host_concurrency)
        async with httpx.AsyncClient(
            headers={"User-Agent": os.getenv("SCRAPER_USER_AGENT", "SCPA-LinkChecker/1.0")}
        ) as client:

            async def _run_host(host_jobs: list[Mapping]) -> None:
                async with semaphore:
                    await self._check_host_jobs(client, host_jobs, counts)

            # return_exceptions: a failing host task must not cancel the others.
            results = await asyncio.gather(
                *(_run_host(js) for js in by_host.values()), return_exceptions=True
            )
            for item in results:
                if isinstance(item, BaseException):
                    logger.error("link check host batch failed: %s", item)

        summary = CycleSummary(
            cycle_number=cycle_number,
            started_at=started,
            finished_at=_utcnow().isoformat(),
            checked=len(batch),
            counts=counts,
        )
        self._write_report(summary)
        logger.info("link_status_cycle=%s", json.dumps(asdict(summary)))
        return summary

    async def run(self) -> list[CycleSummary]:
        cycles: list[CycleSummary] = []
        cycle_number = 0
        self._prepare_report_dir()
        while not self._stop_event.is_set():
            cycle_number += 1
            # A failed cycle (e.g. DB down during batch load) logs and waits for
            # the next interval instead of exiting the run-forever process.
            try:
                cycles.append(await self.run_cycle(cycle_number))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("link check cycle %s failed: %s", cycle_number, exc)
            if self.config.test_max_cycles is not None and cycle_number >= self.config.test_max_cycles:
                break
            if not self.config.run_forever and self.config.test_max_cycles is None:
                break
            if self._stop_event.is_set():
                break
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.check_interval_seconds
                )
            except (TimeoutError, asyncio.TimeoutError):
                pass
        return cycles

    def _prepare_report_dir(self) -> None:
        if self.config.report_dir is not None:
            self.config.report_dir.mkdir(parents=True, exist_ok=True)

    def _write_report(self, summary: CycleSummary) -> None:
        if self.config.report_dir is None:
            return
        path = self.config.report_dir / "cycles.ndjson"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(summary), sort_keys=True) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-check job link/application status.")
    parser.add_argument("--run-forever", action="store_true")
    parser.add_argument("--batch-limit", type=int, default=None)
    parser.add_argument("--test-max-cycles", type=int, default=None)
    parser.add_argument("--report-dir", default=None)
    return parser


def _config_from_args(args: argparse.Namespace) -> LinkCheckConfig:
    config = LinkCheckConfig.from_env()
    overrides = {
        "run_forever": args.run_forever or config.run_forever,
        "batch_limit": args.batch_limit or config.batch_limit,
        "test_max_cycles": (
            args.test_max_cycles if args.test_max_cycles is not None else config.test_max_cycles
        ),
        "report_dir": Path(args.report_dir) if args.report_dir else config.report_dir,
    }
    return LinkCheckConfig(**{**asdict(config), **overrides})


async def _async_main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)
    checker = LinkStatusChecker(config=config)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, checker.stop)
        except NotImplementedError:  # pragma: no cover - Windows
            signal.signal(sig, lambda *_a: checker.stop())
    cycles = await checker.run()
    logger.info("link_status_checker finished cycles=%s", len(cycles))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
