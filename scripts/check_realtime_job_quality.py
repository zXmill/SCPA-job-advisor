"""Check that realtime job data in PostgreSQL satisfies product-quality gates."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.pipeline.continuous_scraper import (  # noqa: E402
    DEFAULT_ALLOWED_SOURCES,
    DEFAULT_MIN_DESCRIPTION_CHARS,
    load_quality_guard_summary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate realtime jobs stored in PostgreSQL.")
    parser.add_argument("--min-description-chars", type=int, default=DEFAULT_MIN_DESCRIPTION_CHARS)
    parser.add_argument("--allowed-sources", default=",".join(DEFAULT_ALLOWED_SOURCES))
    parser.add_argument("--api-base-url", default=None, help="Optional gateway URL for /api/jobs DB-backed check.")
    return parser


async def _async_main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    allowed_sources = tuple(
        source.strip().lower()
        for source in args.allowed_sources.split(",")
        if source.strip()
    )
    summary = await load_quality_guard_summary(
        min_description_chars=args.min_description_chars,
        allowed_sources=allowed_sources,
        api_base_url=args.api_base_url,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0 if summary.passed else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
