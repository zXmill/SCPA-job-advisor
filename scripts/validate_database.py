#!/usr/bin/env python3
"""Validation script for SCPA database setup
Run: python scripts/validate_database.py
"""
import psycopg2
import os
import sys

def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL is required. Copy .env.example to .env or set it in the shell.")
        sys.exit(2)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url

required_tables = [
    'users', 'jobs', 'applications', 'user_skills', 'user_interactions'
]

required_indexes = [
    'idx_users_email', 'idx_jobs_company', 'idx_applications_user',
    'idx_applications_job', 'idx_user_skills_user_user_id_skill_key',
]

def validate():
    try:
        conn = psycopg2.connect(database_url())
        conn.autocommit = True
        cur = conn.cursor()

        print("=" * 60)
        print("SCPA DATABASE VALIDATION")
        print("=" * 60)

        # 1. Check tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        existing_tables = {row[0] for row in cur.fetchall()}

        print("\n[1] TABLE CHECK")
        for table in required_tables:
            status = "OK" if table in existing_tables else "MISSING"
            print(f"  {status} {table}")

        # 2. Check indexes
        print("\n[2] INDEX CHECK")
        cur.execute("""
            SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
        """)
        existing_indexes = {row[0] for row in cur.fetchall()}
        for idx in required_indexes:
            status = "OK" if idx[:63] in [i[:63] for i in existing_indexes] else "MISSING"
            print(f"  {status} {idx[:50]}")

        # 3. Check row counts
        print("\n[3] ROW COUNTS")
        for table in required_tables:
            if table in existing_tables:
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {table}: {count} rows")

        # 4. Check UUID extension
        print("\n[4] EXTENSIONS")
        cur.execute("SELECT * FROM pg_extension WHERE extname = 'uuid-ossp'")
        ext = cur.fetchone()
        print(f"  uuid-ossp: {'OK INSTALLED' if ext else 'MISSING'}")

        # 5. Check ENUMs
        print("\n[5] ENUM TYPES")
        for enum_name in ['userrole', 'jobtype', 'employmentmode', 'experiencelevel',
                          'jobsource', 'applicationstatus', 'skillcategory', 'proficiencylevel']:
            cur.execute("SELECT * FROM pg_type WHERE typname = %s", (enum_name,))
            exists = cur.fetchone()
            print(f"  {enum_name}: {'OK' if exists else 'MISSING'}")

        print("\n" + "=" * 60)
        print("Validation complete")
        print("=" * 60)

        conn.close()
    except psycopg2.Error as e:
        print(f"\nDATABASE CONNECTION FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    validate()
