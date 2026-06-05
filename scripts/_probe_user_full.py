"""Full profile probe: user row + skills + applications by email."""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _probe_user_full.py <email>")
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
            "SELECT id, name, email, role, program_studi, university, "
            "completion_percent, created_at, last_login_at "
            "FROM users WHERE email = $1",
            email,
        )
        if not row:
            print(f"NOT_FOUND: {email}")
            return 1

        print("USER:")
        for k, v in dict(row).items():
            print(f"  {k:<22} = {v}")

        skills = await conn.fetch(
            "SELECT skill, category, proficiency_level "
            "FROM user_skills WHERE user_id = $1 ORDER BY skill",
            row["id"],
        )
        print(f"\nSKILLS ({len(skills)}):")
        for s in skills:
            print(
                f"  - {s['skill']:<24} "
                f"category={s['category']:<10} "
                f"level={s['proficiency_level']}"
            )

        apps = await conn.fetch(
            "SELECT a.status, a.applied_at, j.title, j.company "
            "FROM applications a JOIN jobs j ON a.job_id = j.id "
            "WHERE a.user_id = $1 ORDER BY a.applied_at DESC",
            row["id"],
        )
        print(f"\nAPPLICATIONS ({len(apps)}):")
        for a in apps:
            print(
                f"  - {a['status']:<12} "
                f"{a['title']:<28} @ {a['company']}"
            )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
