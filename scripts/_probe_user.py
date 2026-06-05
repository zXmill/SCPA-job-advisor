"""Quick probe: look up a user by email in db_scpa and print the row.

Usage:
    python scripts/_probe_user.py <email>
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _probe_user.py <email>")
        return 1
    email = sys.argv[1]
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "db_scpa")
    dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET lc_messages = 'C'")
        row = await conn.fetchrow(
            "SELECT id, name, email, role, completion_percent, created_at "
            "FROM users WHERE email = $1",
            email,
        )
        if row:
            for k, v in dict(row).items():
                print(f"  {k:<22} = {v}")
        else:
            print(f"NOT_FOUND: {email}")
        total = await conn.fetchval("SELECT count(*) FROM users")
        print(f"\nTOTAL_USERS: {total}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
