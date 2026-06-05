"""Convert source column from enum to varchar for scraper flexibility."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is required.")
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

async def migrate():
    e = create_async_engine(_database_url())
    async with e.begin() as c:
        await c.execute(text("ALTER TABLE jobs ALTER COLUMN source TYPE varchar(50) USING source::text"))
        print("[OK] Converted source column to varchar(50)")

        r = await c.execute(text("SELECT source, COUNT(*) FROM jobs GROUP BY source"))
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")
    await e.dispose()

asyncio.run(migrate())
