"""Delete browser/smoke test users from db_scpa.

Use after manual end-to-end testing through the frontend so the real
database stays clean and only contains the seeded baseline users.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()


PATTERNS = [
    "browser_test_%@example.com",
    "final_verify_%@example.com",
    "smoke_%@example.com",
]


async def main() -> int:
    user = os.environ.get("POSTGRES_USER", "postgres")
    pwd = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "db_scpa")
    dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET lc_messages = 'C'")
        for pat in PATTERNS:
            status = await conn.execute(
                "DELETE FROM users WHERE email LIKE $1", pat
            )
            print(f"  pattern={pat:<32} -> {status}")
        total = await conn.fetchval("SELECT count(*) FROM users")
        print(f"\nremaining users: {total}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
