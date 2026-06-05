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

async def check():
    e = create_async_engine(_database_url())
    async with e.connect() as c:
        r = await c.execute(text("SELECT udt_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='source'"))
        enum_name = r.scalar()
        print("Source column type:", enum_name)

        if enum_name and enum_name != "varchar" and enum_name != "text":
            r2 = await c.execute(text(f"SELECT unnest(enum_range(NULL::{enum_name}))"))
            print("Enum values:", [row[0] for row in r2.fetchall()])

        r3 = await c.execute(text("SELECT COUNT(*) FROM jobs"))
        print("Job count:", r3.scalar())

        r4 = await c.execute(text("SELECT source, COUNT(*) FROM jobs GROUP BY source"))
        for row in r4.fetchall():
            print(f"  {row[0]}: {row[1]}")
    await e.dispose()

asyncio.run(check())
