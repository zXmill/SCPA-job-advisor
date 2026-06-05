"""Bounded and long-running continuous realtime scraping worker.

The worker keeps the existing `/scrape/run` and `/pipeline/run` request paths
finite. It runs as a separate process, repeatedly executing one scrape/upsert
cycle through pipeline stage 1, then recording quality evidence for the DB.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import inspect
import json
import logging
import os
from pathlib import Path
import random
import signal
import time
from typing import Any

import httpx
from sqlalchemy import text

try:  # Local harness runs can reuse the repo .env; containers already use env.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - pipeline image receives explicit env.
    pass

from .stages.stage_1_scrape import _get_db_engine, run_scrape_stage


logger = logging.getLogger("scpa.pipeline.continuous_scraper")
DEFAULT_REPORT_DIR = Path("reports/debug/continuous_scrape")
DEFAULT_ALLOWED_SOURCES = (
    "kalibrr",
    "linkedin",
    "jobstreet",
    "glints",
    "karir",
    "techinasia",
    "indeed",
)
DEFAULT_MIN_DESCRIPTION_CHARS = 300


@dataclass(frozen=True)
class ContinuousScrapeConfig:
    continuous_enabled: bool = False
    scraper_url: str = "http://scraper:8001"
    cycle_limit: int = 10
    cycle_interval_seconds: float = 900.0
    max_empty_cycles_before_backoff: int = 3
    backoff_min_seconds: float = 60.0
    backoff_max_seconds: float = 1800.0
    allowed_sources: tuple[str, ...] = DEFAULT_ALLOWED_SOURCES
    run_forever: bool = False
    test_max_cycles: int | None = 1
    report_dir: Path | None = DEFAULT_REPORT_DIR
    min_description_chars: int = DEFAULT_MIN_DESCRIPTION_CHARS
    jitter_seconds: float = 0.0
    active_job_target: int = 0
    catch_up_interval_seconds: float = 60.0
    catch_up_cycle_limit: int = 1000
    seed_rotation_stride: int = 6

    @classmethod
    def from_env(cls) -> "ContinuousScrapeConfig":
        test_max_cycles_raw = os.getenv("SCRAPER_TEST_MAX_CYCLES", "").strip()
        test_max_cycles = int(test_max_cycles_raw) if test_max_cycles_raw else None
        run_forever = _env_bool("SCRAPER_RUN_FOREVER", False)
        if not run_forever and test_max_cycles is None:
            test_max_cycles = 1
        allowed_sources = tuple(
            source.strip().lower()
            for source in os.getenv("SCRAPER_ALLOWED_SOURCES", ",".join(DEFAULT_ALLOWED_SOURCES)).split(",")
            if source.strip()
        )
        report_dir_raw = os.getenv("SCRAPER_REPORT_DIR", str(DEFAULT_REPORT_DIR)).strip()
        return cls(
            continuous_enabled=_env_bool("SCRAPER_CONTINUOUS_ENABLED", False),
            scraper_url=os.getenv("SCRAPER_URL", "http://scraper:8001").rstrip("/"),
            cycle_limit=max(1, int(os.getenv("SCRAPER_CYCLE_LIMIT", os.getenv("PIPELINE_SCRAPE_REFRESH_LIMIT", "10")))),
            cycle_interval_seconds=max(0.0, float(os.getenv("SCRAPER_CYCLE_INTERVAL_SECONDS", "900"))),
            max_empty_cycles_before_backoff=max(
                1, int(os.getenv("SCRAPER_MAX_EMPTY_CYCLES_BEFORE_BACKOFF", "3"))
            ),
            backoff_min_seconds=max(0.0, float(os.getenv("SCRAPER_BACKOFF_MIN_SECONDS", "60"))),
            backoff_max_seconds=max(0.0, float(os.getenv("SCRAPER_BACKOFF_MAX_SECONDS", "1800"))),
            allowed_sources=allowed_sources or DEFAULT_ALLOWED_SOURCES,
            run_forever=run_forever,
            test_max_cycles=test_max_cycles,
            report_dir=Path(report_dir_raw) if report_dir_raw else None,
            min_description_chars=max(
                1, int(os.getenv("SCRAPER_QUALITY_MIN_DESC_CHARS", str(DEFAULT_MIN_DESCRIPTION_CHARS)))
            ),
            jitter_seconds=max(0.0, float(os.getenv("SCRAPER_CYCLE_JITTER_SECONDS", "0"))),
            active_job_target=max(0, int(os.getenv("SCRAPER_ACTIVE_JOB_TARGET", "0"))),
            catch_up_interval_seconds=max(0.0, float(os.getenv("SCRAPER_CATCH_UP_INTERVAL_SECONDS", "60"))),
            catch_up_cycle_limit=max(
                1,
                int(os.getenv("SCRAPER_CATCH_UP_CYCLE_LIMIT", os.getenv("SCRAPER_ACTIVE_JOB_TARGET", "1000"))),
            ),
            seed_rotation_stride=max(0, int(os.getenv("SCRAPER_SEED_ROTATION_STRIDE", "6"))),
        )


@dataclass(frozen=True)
class QualityGuardSummary:
    total_jobs: int
    sample_jobs: int
    under_min_description: int
    no_skill_signal: int
    missing_source_url: int
    generic_listing_descriptions: int
    sources: dict[str, int]
    min_description_length: int | None
    avg_description_length: float | None
    max_description_length: int | None
    disallowed_sources: dict[str, int] = field(default_factory=dict)
    app_api_total: int | None = None
    app_api_db_total_mismatch: bool = False

    @property
    def passed(self) -> bool:
        return (
            self.sample_jobs == 0
            and self.under_min_description == 0
            and self.no_skill_signal == 0
            and self.missing_source_url == 0
            and self.generic_listing_descriptions == 0
            and not self.disallowed_sources
            and not self.app_api_db_total_mismatch
        )


@dataclass(frozen=True)
class CycleSummary:
    cycle_number: int
    started_at: str
    finished_at: str
    duration_seconds: float
    accepted_jobs: int
    rejected_jobs: int
    rejection_reasons: dict[str, int]
    upserted_jobs: int
    db_total_before: int
    db_total_after: int
    estimated_inserted_jobs: int
    estimated_updated_or_duplicate_jobs: int
    source_stats: list[dict[str, Any]]
    quality_guard: QualityGuardSummary
    next_sleep_seconds: float

    @property
    def passed(self) -> bool:
        return self.quality_guard.passed


@dataclass(frozen=True)
class ContinuousRunSummary:
    cycles: int
    stopped_reason: str
    started_at: str
    finished_at: str
    cycle_summaries: list[CycleSummary] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(cycle.passed for cycle in self.cycle_summaries)


CycleCallable = Callable[[int], Awaitable[Mapping[str, Any]]]
GuardCallable = Callable[[], Awaitable[QualityGuardSummary]]
SleepCallable = Callable[[float], Awaitable[None] | None]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def calculate_sleep_seconds(config: ContinuousScrapeConfig, empty_cycle_streak: int) -> float:
    if empty_cycle_streak < config.max_empty_cycles_before_backoff:
        base = config.cycle_interval_seconds
    else:
        exponent = empty_cycle_streak - config.max_empty_cycles_before_backoff
        base = min(config.backoff_max_seconds, config.backoff_min_seconds * (2**exponent))
    if config.jitter_seconds <= 0:
        return round(base, 3)
    return round(base + random.uniform(0, config.jitter_seconds), 3)


def calculate_next_sleep_seconds(
    config: ContinuousScrapeConfig, empty_cycle_streak: int, total_active_jobs: int
) -> float:
    base_sleep = calculate_sleep_seconds(config, empty_cycle_streak)
    if (
        config.run_forever
        and config.active_job_target > 0
        and total_active_jobs < config.active_job_target
        and config.catch_up_interval_seconds < base_sleep
    ):
        return round(config.catch_up_interval_seconds, 3)
    return base_sleep


def calculate_effective_cycle_limit(config: ContinuousScrapeConfig, total_active_jobs: int) -> int:
    """Use a larger bounded scrape batch while the runtime catalog is below target."""
    if not config.run_forever or config.active_job_target <= 0:
        return config.cycle_limit
    deficit = config.active_job_target - total_active_jobs
    if deficit <= 0:
        return config.cycle_limit
    return max(config.cycle_limit, min(config.catch_up_cycle_limit, deficit))


def calculate_seed_offset(config: ContinuousScrapeConfig, cycle_number: int) -> int:
    """Rotate source query buckets between cycles so run-forever expands coverage."""
    if cycle_number <= 1 or config.seed_rotation_stride <= 0:
        return 0
    return (cycle_number - 1) * config.seed_rotation_stride


async def _maybe_await(value: Awaitable[None] | None) -> None:
    if inspect.isawaitable(value):
        await value


async def load_quality_guard_summary(
    *,
    min_description_chars: int = DEFAULT_MIN_DESCRIPTION_CHARS,
    allowed_sources: tuple[str, ...] = DEFAULT_ALLOWED_SOURCES,
    api_base_url: str | None = None,
) -> QualityGuardSummary:
    engine = _get_db_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL/GATEWAY_DATABASE_URL is required for continuous scrape quality guard")
    desc_expr = "coalesce(nullif(description_text, ''), description, '')"
    generic_expr = (
        f"lower({desc_expr}) LIKE '%temukan lebih dari%' OR "
        f"lower({desc_expr}) LIKE '%lowongan kerja dan loker terbaru%' OR "
        f"lower({desc_expr}) LIKE '%lamar cepat, cukup sekali tap%' OR "
        f"lower({desc_expr}) LIKE '%explore jobs%' OR "
        f"lower({desc_expr}) LIKE '%search jobs%'"
    )
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total_jobs,
                        COUNT(*) FILTER (
                            WHERE source::text = 'sample'
                               OR lower(coalesce(source_url, '')) LIKE 'sample:%'
                        ) AS sample_jobs,
                        COUNT(*) FILTER (WHERE coalesce(source_url, '') = '') AS missing_source_url,
                        COUNT(*) FILTER (WHERE length({desc_expr}) < :min_desc) AS under_min_description,
                        COUNT(*) FILTER (
                            WHERE cardinality(coalesce(required_skill_names, '{{}}'::text[]))
                                + cardinality(coalesce(preferred_skill_names, '{{}}'::text[]))
                                + cardinality(coalesce(extracted_skill_names, '{{}}'::text[])) = 0
                        ) AS no_skill_signal,
                        COUNT(*) FILTER (WHERE {generic_expr}) AS generic_listing_descriptions,
                        MIN(length({desc_expr})) AS min_description_length,
                        AVG(length({desc_expr})) AS avg_description_length,
                        MAX(length({desc_expr})) AS max_description_length
                    FROM jobs
                    WHERE is_active = true
                    """
                ),
                {"min_desc": min_description_chars},
            )
        ).mappings().one()
        source_rows = (
            await conn.execute(
                text(
                    """
                    SELECT coalesce(source::text, 'unknown') AS source, COUNT(*) AS jobs
                    FROM jobs
                    WHERE is_active = true
                    GROUP BY coalesce(source::text, 'unknown')
                    ORDER BY jobs DESC, source
                    """
                )
            )
        ).mappings().all()

    app_api_total: int | None = None
    if api_base_url:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{api_base_url.rstrip('/')}/api/jobs", params={"page": 1, "limit": 10})
            response.raise_for_status()
            payload = response.json()
            app_api_total = int(payload.get("total") or len(payload.get("jobs", [])))

    sources = {str(item["source"]): int(item["jobs"] or 0) for item in source_rows}
    allowed = {source.lower() for source in allowed_sources}
    disallowed_sources = {
        source: count
        for source, count in sources.items()
        if allowed and source.lower() not in allowed
    }
    total_jobs = int(row["total_jobs"] or 0)
    return QualityGuardSummary(
        total_jobs=total_jobs,
        sample_jobs=int(row["sample_jobs"] or 0),
        under_min_description=int(row["under_min_description"] or 0),
        no_skill_signal=int(row["no_skill_signal"] or 0),
        missing_source_url=int(row["missing_source_url"] or 0),
        generic_listing_descriptions=int(row["generic_listing_descriptions"] or 0),
        sources=sources,
        min_description_length=int(row["min_description_length"]) if row["min_description_length"] is not None else None,
        avg_description_length=round(float(row["avg_description_length"]), 1)
        if row["avg_description_length"] is not None
        else None,
        max_description_length=int(row["max_description_length"]) if row["max_description_length"] is not None else None,
        disallowed_sources=disallowed_sources,
        app_api_total=app_api_total,
        app_api_db_total_mismatch=app_api_total is not None and app_api_total != total_jobs,
    )


class ContinuousScrapeRunner:
    def __init__(
        self,
        *,
        config: ContinuousScrapeConfig,
        cycle_callable: CycleCallable | None = None,
        guard_callable: GuardCallable | None = None,
        sleep_callable: SleepCallable | None = None,
    ) -> None:
        self.config = config
        self._cycle_callable = cycle_callable or self._run_one_cycle
        self._guard_callable = guard_callable or self._load_guard
        self._sleep_callable = sleep_callable or asyncio.sleep
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def _load_guard(self) -> QualityGuardSummary:
        return await load_quality_guard_summary(
            min_description_chars=self.config.min_description_chars,
            allowed_sources=self.config.allowed_sources,
        )

    async def _run_one_cycle(self, cycle_number: int) -> Mapping[str, Any]:
        before = await self._load_guard()
        effective_limit = calculate_effective_cycle_limit(self.config, before.total_jobs)
        seed_offset = calculate_seed_offset(self.config, cycle_number)
        async with httpx.AsyncClient(timeout=max(30.0, float(os.getenv("SCRAPER_RUN_TIMEOUT_SECONDS", "180")))) as client:
            result = await run_scrape_stage(
                client=client,
                scraper_url=self.config.scraper_url,
                user_id="continuous-scraper",
                profile={"program_studi": "mixed", "jurusan": "mixed", "skills": []},
                interaction_count=0,
                refresh_jobs=True,
                limit=effective_limit,
                seed_offset=seed_offset,
            )
        after = await self._load_guard()
        summary = result.summary
        scraper_meta = summary.get("scraper") if isinstance(summary.get("scraper"), dict) else {}
        quality_gate = scraper_meta.get("quality_gate") if isinstance(scraper_meta.get("quality_gate"), dict) else {}
        upserted = int(summary.get("upserted_jobs") or 0)
        inserted = max(0, after.total_jobs - before.total_jobs)
        return {
            "cycle_number": cycle_number,
            "accepted_jobs": int(scraper_meta.get("count") or summary.get("scraped_jobs") or 0),
            "upserted": upserted,
            "db_total_before": before.total_jobs,
            "db_total_after": after.total_jobs,
            "estimated_inserted_jobs": inserted,
            "estimated_updated_or_duplicate_jobs": max(0, upserted - inserted),
            "quality_rejections": quality_gate.get("rejection_reasons") or {},
            "rejected_jobs": int(quality_gate.get("rejected") or 0),
            "source_stats": scraper_meta.get("source_stats") or [],
            "requested_limit": effective_limit,
            "seed_offset": seed_offset,
        }

    async def run(self) -> ContinuousRunSummary:
        started_at = _utc_now()
        cycles: list[CycleSummary] = []
        empty_streak = 0
        stopped_reason = "stopped"
        cycle_number = 0
        self._prepare_report_dir()
        while not self._stop_event.is_set():
            cycle_number += 1
            cycle_started = _utc_now()
            perf_start = time.perf_counter()
            cycle_data = dict(await self._cycle_callable(cycle_number))
            guard = await self._guard_callable()
            accepted_jobs = int(cycle_data.get("accepted_jobs") or 0)
            empty_streak = empty_streak + 1 if accepted_jobs == 0 else 0
            next_sleep = calculate_next_sleep_seconds(self.config, empty_streak, guard.total_jobs)
            cycle = CycleSummary(
                cycle_number=cycle_number,
                started_at=cycle_started,
                finished_at=_utc_now(),
                duration_seconds=round(time.perf_counter() - perf_start, 3),
                accepted_jobs=accepted_jobs,
                rejected_jobs=int(cycle_data.get("rejected_jobs") or 0),
                rejection_reasons=dict(cycle_data.get("quality_rejections") or {}),
                upserted_jobs=int(cycle_data.get("upserted") or 0),
                db_total_before=int(cycle_data.get("db_total_before") or 0),
                db_total_after=int(cycle_data.get("db_total_after") or guard.total_jobs),
                estimated_inserted_jobs=int(cycle_data.get("estimated_inserted_jobs") or 0),
                estimated_updated_or_duplicate_jobs=int(
                    cycle_data.get("estimated_updated_or_duplicate_jobs") or 0
                ),
                source_stats=list(cycle_data.get("source_stats") or []),
                quality_guard=guard,
                next_sleep_seconds=next_sleep,
            )
            cycles.append(cycle)
            self._write_cycle(cycle)
            logger.info("continuous_scrape_cycle=%s", json.dumps(asdict(cycle), default=_json_default))

            if self.config.test_max_cycles is not None and cycle_number >= self.config.test_max_cycles:
                stopped_reason = "test_max_cycles"
                break
            if not self.config.run_forever and self.config.test_max_cycles is None:
                stopped_reason = "bounded_once"
                break
            if self._stop_event.is_set():
                stopped_reason = "signal"
                break
            await _maybe_await(self._sleep_callable(next_sleep))
        summary = ContinuousRunSummary(
            cycles=len(cycles),
            stopped_reason=stopped_reason,
            started_at=started_at,
            finished_at=_utc_now(),
            cycle_summaries=cycles,
        )
        self._write_summary(summary)
        return summary

    def _prepare_report_dir(self) -> None:
        if self.config.report_dir is None:
            return
        (self.config.report_dir).mkdir(parents=True, exist_ok=True)

    def _write_cycle(self, cycle: CycleSummary) -> None:
        if self.config.report_dir is None:
            return
        path = self.config.report_dir / "cycles.ndjson"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(cycle), default=_json_default, sort_keys=True) + "\n")

    def _write_summary(self, summary: ContinuousRunSummary) -> None:
        if self.config.report_dir is None:
            return
        path = self.config.report_dir / "summary.json"
        path.write_text(json.dumps(asdict(summary), indent=2, default=_json_default, sort_keys=True), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run continuous realtime scrape cycles.")
    parser.add_argument("--cycle-limit", type=int, default=None)
    parser.add_argument("--test-max-cycles", type=int, default=None)
    parser.add_argument("--cycle-interval-seconds", type=float, default=None)
    parser.add_argument("--run-forever", action="store_true")
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--api-base-url", default=None, help="Optional app API URL for DB-backed API guard evidence.")
    return parser


def _config_from_args(args: argparse.Namespace) -> ContinuousScrapeConfig:
    config = ContinuousScrapeConfig.from_env()
    return ContinuousScrapeConfig(
        **{
            **asdict(config),
            "cycle_limit": args.cycle_limit or config.cycle_limit,
            "test_max_cycles": args.test_max_cycles if args.test_max_cycles is not None else config.test_max_cycles,
            "cycle_interval_seconds": (
                args.cycle_interval_seconds
                if args.cycle_interval_seconds is not None
                else config.cycle_interval_seconds
            ),
            "run_forever": args.run_forever or config.run_forever,
            "report_dir": Path(args.report_dir) if args.report_dir else config.report_dir,
        }
    )


async def _async_main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)
    runner = ContinuousScrapeRunner(config=config)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, runner.stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: runner.stop())
    summary = await runner.run()
    payload = asdict(summary)
    if args.api_base_url:
        payload["api_guard"] = asdict(
            await load_quality_guard_summary(
                min_description_chars=config.min_description_chars,
                allowed_sources=config.allowed_sources,
                api_base_url=args.api_base_url,
            )
        )
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    return 0 if summary.passed else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
