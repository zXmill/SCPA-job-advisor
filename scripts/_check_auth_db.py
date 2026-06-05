"""Quick auth-DB readiness probe — used during test bring-up.

Verifies the SCPA Postgres instance is reachable, the auth-relevant
tables exist, and reports current row counts. Safe to run anytime
(read-only).
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from dotenv import load_dotenv


load_dotenv()


def _resolve_dsn() -> str:
    """Return a plain asyncpg DSN derived from DATABASE_URL/.env."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is required.")
    # Strip SQLAlchemy driver suffixes for raw asyncpg.connect
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break
    # asyncpg does not accept ?ssl=prefer query — drop it
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


def _masked_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.password:
        return url
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}" if username else f"***@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


async def main() -> int:
    dsn = _resolve_dsn()
    print(f"DSN: {_masked_url(dsn)}")
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:
        print(f"CONN_FAIL: {exc}")
        return 1

    try:
        ver = await conn.fetchval("SELECT version()")
        print(f"VER: {ver[:80]}")

        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' ORDER BY tablename"
        )
        names = [r["tablename"] for r in tables]
        print(f"TABLES: {names}")

        required = {"users", "user_skills", "jobs", "applications"}
        missing = required - set(names)
        if missing:
            print(f"MISSING_TABLES: {sorted(missing)}")
        else:
            print("MISSING_TABLES: none")

        for tbl in ("users", "user_skills", "jobs", "applications"):
            if tbl in names:
                try:
                    cnt = await conn.fetchval(f"SELECT count(*) FROM {tbl}")
                    print(f"{tbl.upper()}_COUNT: {cnt}")
                except Exception as exc:
                    print(f"{tbl.upper()}_ERR: {exc}")

        # Inspect users column layout the gateway depends on
        if "users" in names:
            cols = await conn.fetch(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='users' "
                "ORDER BY ordinal_position"
            )
            print("USERS_COLUMNS:")
            for row in cols:
                print(
                    f"  - {row['column_name']:<22} "
                    f"{row['data_type']:<25} "
                    f"null={row['is_nullable']}"
                )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
