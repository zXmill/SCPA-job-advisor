"""Idempotently bootstrap the SCPA backend test database.

Creates ``db_scpa_test`` if it does not yet exist by issuing
``CREATE DATABASE`` against the cluster's default ``postgres`` DB.
Safe to run multiple times.

Usage::

    python scripts/_ensure_test_db.py
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv


load_dotenv()


TEST_DB_NAME = os.environ.get("SCPA_TEST_DB", "db_scpa_test")


def _admin_dsn() -> str:
    """Return a DSN pointing at the cluster's default ``postgres`` DB."""
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@{host}:{port}/postgres"


async def main() -> int:
    dsn = _admin_dsn()
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:
        print(f"ADMIN_CONN_FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
        )
        if exists:
            print(f"TEST_DB_EXISTS: {TEST_DB_NAME}")
            return 0
        # CREATE DATABASE cannot run in a transaction block — asyncpg's
        # implicit autocommit makes this safe.
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        print(f"TEST_DB_CREATED: {TEST_DB_NAME}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
