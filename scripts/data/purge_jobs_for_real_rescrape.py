"""Purge local job data before a real-data rescrape.

This script intentionally targets only job-derived tables and refuses to run
without an explicit confirmation flag. It does not create sample jobs.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


JOB_TABLES = (
    "feedback_events",
    "served_slate_items",
    "served_slates",
    "user_job_interactions",
    "user_interactions",
    "applications",
    "skill_gap_snapshots",
    "job_required_skills",
    "jobs",
)

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}


def _async_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _database_url() -> str:
    raw_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("GATEWAY_DATABASE_URL")
        or os.getenv("PIPELINE_DATABASE_URL")
        or "postgresql+asyncpg://postgres:AdminPass456@localhost:5432/db_scpa"
    )
    return _async_db_url(raw_url)


def _ensure_local_database(url: str) -> None:
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    if parsed.hostname not in LOCAL_DB_HOSTS:
        raise SystemExit(f"Refusing to purge non-local database host: {parsed.hostname}")
    if os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}:
        raise SystemExit("Refusing to purge when APP_ENV is production")


async def _purge(url: str, *, reset_skills: bool) -> dict[str, int]:
    engine = create_async_engine(url, pool_pre_ping=True)
    tables = [*JOB_TABLES, "skills"] if reset_skills else list(JOB_TABLES)
    joined = ", ".join(tables)
    async with engine.begin() as conn:
        before = {}
        for table in tables:
            before[table] = int((await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one())
        await conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
    await engine.dispose()
    return before


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge local job data before real scraping.")
    parser.add_argument("--confirm-real-data-rescrape", action="store_true", required=True)
    parser.add_argument(
        "--reset-skills",
        action="store_true",
        help="Also clear skills so the ESCO/O*NET taxonomy is reseeded by the gateway.",
    )
    args = parser.parse_args()

    url = _database_url()
    _ensure_local_database(url)
    counts = asyncio.run(_purge(url, reset_skills=args.reset_skills))
    print({"purged": counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
