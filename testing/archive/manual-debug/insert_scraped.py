"""Insert scraped jobs directly into the DB, bypassing pipeline limits."""
import asyncio
import json
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:AdminPass456@localhost:5432/db_scpa",
)


def _to_uuid(value: str):
    import uuid
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(value))


async def main():
    engine = create_async_engine(DB_URL.replace("+psycopg2", "+asyncpg"), pool_pre_ping=True)
    with open(r"e:/TUGAS AKHIR/SCPA/scrape_1000.json", encoding="utf-8") as f:
        data = json.load(f)
    jobs = data.get("jobs", [])
    print(f"Inserting {len(jobs)} jobs...")

    async with engine.begin() as conn:
        # First clear existing jobs
        await conn.execute(text("DELETE FROM jobs"))
        print("Cleared existing jobs.")

        params = []
        for job in jobs:
            job_id = str(job.get("job_id") or job.get("id") or job.get("content_hash"))
            params.append({
                "id": _to_uuid(job_id),
                "title": job.get("title") or "Untitled",
                "company": job.get("company") or "Unknown",
                "company_logo": job.get("company_logo"),
                "location": job.get("location") or None,
                "description": job.get("description") or None,
                "salary_text": job.get("salary_text") or None,
                "source": job.get("source") or "scraper",
                "is_active": True,
                "match_data": json.dumps({
                    "original_job_id": job_id,
                    "source_url": job.get("source_url"),
                    "skills": job.get("skills") or job.get("tags") or [],
                    "tags": job.get("tags") or [],
                }),
                "posted_at": datetime.utcnow(),
            })

        if params:
            await conn.execute(
                text(
                    "INSERT INTO jobs (id, title, company, company_logo, location, description, salary_text, source, is_active, match_data, posted_at) "
                    "VALUES (:id, :title, :company, :company_logo, :location, :description, :salary_text, :source, :is_active, CAST(:match_data AS jsonb), :posted_at) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "title = EXCLUDED.title, company = EXCLUDED.company, company_logo = EXCLUDED.company_logo, "
                    "location = EXCLUDED.location, description = EXCLUDED.description, salary_text = EXCLUDED.salary_text, "
                    "source = EXCLUDED.source, is_active = EXCLUDED.is_active, match_data = EXCLUDED.match_data, posted_at = EXCLUDED.posted_at"
                ),
                params,
            )
        print(f"Inserted {len(params)} jobs.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
