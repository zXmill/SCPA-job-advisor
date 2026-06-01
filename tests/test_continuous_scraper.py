"""Contracts for bounded continuous realtime scraping."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from services.pipeline.continuous_scraper import (
    ContinuousScrapeConfig,
    ContinuousScrapeRunner,
    QualityGuardSummary,
    calculate_sleep_seconds,
)


def _guard(total: int = 7) -> QualityGuardSummary:
    return QualityGuardSummary(
        total_jobs=total,
        sample_jobs=0,
        under_min_description=0,
        no_skill_signal=0,
        missing_source_url=0,
        generic_listing_descriptions=0,
        sources={"kalibrr": total},
        min_description_length=476,
        avg_description_length=1334.9,
        max_description_length=2655,
    )


@pytest.mark.anyio
async def test_bounded_continuous_runner_stops_after_test_max_cycles() -> None:
    """A local harness run can exercise multiple cycles without running forever."""
    calls: list[int] = []
    sleeps: list[float] = []

    async def fake_cycle(cycle_number: int):
        calls.append(cycle_number)
        return {
            "cycle_number": cycle_number,
            "accepted_jobs": 7,
            "upserted": 7,
            "db_total_before": 7,
            "db_total_after": 7,
            "quality_rejections": {},
        }

    async def fake_guard():
        return _guard(total=7)

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    config = ContinuousScrapeConfig(
        cycle_limit=10,
        cycle_interval_seconds=0.01,
        run_forever=True,
        test_max_cycles=3,
    )
    runner = ContinuousScrapeRunner(
        config=config,
        cycle_callable=fake_cycle,
        guard_callable=fake_guard,
        sleep_callable=fake_sleep,
    )

    summary = await runner.run()

    assert calls == [1, 2, 3]
    assert summary.cycles == 3
    assert summary.stopped_reason == "test_max_cycles"
    assert all(cycle.quality_guard.passed for cycle in summary.cycle_summaries)
    assert sleeps == [0.01, 0.01]


@pytest.mark.anyio
async def test_continuous_runner_rejects_failed_quality_guard() -> None:
    """Accepted jobs must still pass the realtime quality gate after every cycle."""

    async def fake_cycle(cycle_number: int):
        return {
            "cycle_number": cycle_number,
            "accepted_jobs": 1,
            "upserted": 1,
            "db_total_before": 0,
            "db_total_after": 1,
            "quality_rejections": {},
        }

    async def failing_guard():
        return replace(_guard(total=1), under_min_description=1)

    runner = ContinuousScrapeRunner(
        config=ContinuousScrapeConfig(test_max_cycles=1),
        cycle_callable=fake_cycle,
        guard_callable=failing_guard,
        sleep_callable=lambda _seconds: asyncio.sleep(0),
    )

    summary = await runner.run()

    assert summary.cycles == 1
    assert summary.cycle_summaries[0].quality_guard.passed is False
    assert summary.cycle_summaries[0].quality_guard.under_min_description == 1


def test_backoff_increases_after_empty_cycles_and_caps() -> None:
    """Empty cycles should back off without replacing the normal cycle interval forever."""
    config = ContinuousScrapeConfig(
        cycle_interval_seconds=5,
        max_empty_cycles_before_backoff=2,
        backoff_min_seconds=30,
        backoff_max_seconds=90,
    )

    assert calculate_sleep_seconds(config, empty_cycle_streak=0) == 5
    assert calculate_sleep_seconds(config, empty_cycle_streak=1) == 5
    assert calculate_sleep_seconds(config, empty_cycle_streak=2) == 30
    assert calculate_sleep_seconds(config, empty_cycle_streak=3) == 60
    assert calculate_sleep_seconds(config, empty_cycle_streak=5) == 90
