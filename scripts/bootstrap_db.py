"""SCPA database bootstrap — one-command setup for the real database.

Steps performed (all idempotent and safe to re-run):
    1. Ensure the target database exists (CREATE DATABASE if absent).
    2. Apply pending alembic migrations to ``head``.
    3. Verify schema (tables, ENUMs, row counts).
    4. Optionally seed baseline data (3 users, 12 jobs, skills, apps).
    5. Run the auth smoke test through the real gateway.

Usage::

    # Bootstrap the *real* DB (db_scpa) defined in .env
    python scripts/bootstrap_db.py

    # Same, but also drop+re-seed sample data
    python scripts/bootstrap_db.py --seed

    # Bootstrap a *different* database (e.g. for staging)
    python scripts/bootstrap_db.py --database db_scpa_staging
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")


GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def info(msg: str) -> None:
    print(f"{BOLD}>>{RESET} {msg}")


def ok(msg: str) -> None:
    print(f"   {GREEN}OK{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"   {YELLOW}WARN{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"   {RED}FAIL{RESET} {msg}")


def _admin_dsn() -> str:
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@{host}:{port}/postgres"


async def _ensure_database(name: str) -> None:
    """Create the target database if it does not exist."""
    import asyncio  # local import to keep module import-cheap
    _ = asyncio  # noqa: F841

    conn = await asyncpg.connect(_admin_dsn())
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", name
        )
        if exists:
            ok(f"database '{name}' already exists")
            return
        await conn.execute(f'CREATE DATABASE "{name}"')
        ok(f"database '{name}' created")
    finally:
        await conn.close()


def _run_alembic_upgrade(target_url: str) -> bool:
    """Invoke ``alembic upgrade head`` in a subprocess with overridden URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = target_url
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail("alembic upgrade head failed:")
        print(proc.stdout)
        print(proc.stderr)
        return False
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "(no output)"
    ok(f"alembic: {last}")
    return True


async def _verify_schema(target_url_async: str) -> bool:
    """Connect to the target DB and confirm all tables are present."""
    import asyncpg
    # asyncpg DSN: strip SQLAlchemy driver prefix
    raw = target_url_async
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if raw.startswith(prefix):
            raw = "postgresql://" + raw[len(prefix):]
            break
    if "?" in raw:
        raw = raw.split("?", 1)[0]

    conn = await asyncpg.connect(raw)
    try:
        tables = {
            r["tablename"]
            for r in await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        required = {
            "users", "user_skills", "jobs", "applications",
            "user_interactions", "alembic_version",
        }
        missing = required - tables
        if missing:
            fail(f"missing tables: {sorted(missing)}")
            return False
        ok(f"tables present: {sorted(tables)}")
        counts = {}
        for t in ("users", "jobs", "user_skills", "applications"):
            counts[t] = await conn.fetchval(f"SELECT count(*) FROM {t}")
        ok(
            f"row counts: users={counts['users']}, jobs={counts['jobs']}, "
            f"skills={counts['user_skills']}, applications={counts['applications']}"
        )
        return True
    finally:
        await conn.close()


def _run_seed() -> bool:
    """Invoke ``python -m db.seed`` in a subprocess."""
    proc = subprocess.run(
        [sys.executable, "-m", "db.seed"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail("seed failed:")
        print(proc.stdout)
        print(proc.stderr)
        return False
    for line in proc.stdout.strip().splitlines():
        ok(f"seed: {line}")
    return True


def _run_smoke() -> bool:
    """Invoke the auth smoke test in a subprocess."""
    proc = subprocess.run(
        [sys.executable, "scripts/_smoke_auth_realdb.py"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    # Print last 20 lines of output regardless
    tail = proc.stdout.strip().splitlines()[-20:]
    for line in tail:
        print(f"   {DIM}{line}{RESET}")
    if proc.returncode != 0:
        fail("smoke failed")
        return False
    ok("smoke passed")
    return True


async def _amain(args: argparse.Namespace) -> int:
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    target_url_sync = (
        f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{args.database}"
    )
    target_url_async = target_url_sync.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://", 1
    )

    info(f"Target database: {BOLD}{args.database}{RESET}")
    info(f"Host: {host}:{port}")

    info("Step 1/4: Ensure database exists")
    await _ensure_database(args.database)

    info("Step 2/4: Apply alembic migrations")
    if not _run_alembic_upgrade(target_url_sync):
        return 1

    if args.seed:
        info("Step 2.5: Seed baseline data")
        if not _run_seed():
            return 1

    info("Step 3/4: Verify schema")
    if not await _verify_schema(target_url_async):
        return 1

    if args.smoke:
        info("Step 4/4: Run auth smoke test")
        if not _run_smoke():
            return 1
    else:
        warn("Skipping smoke test (pass --smoke to enable)")

    print(f"\n{BOLD}{GREEN}SCPA database bootstrap complete.{RESET}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-command setup for the SCPA database."
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("POSTGRES_DB", "db_scpa"),
        help="Target database name (default: from POSTGRES_DB env var)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Also run db/seed.py to populate baseline data",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run the auth smoke test after bootstrap",
    )
    args = parser.parse_args()

    import asyncio
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
