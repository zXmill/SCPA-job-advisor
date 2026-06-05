#!/usr/bin/env python3
"""Quick script to check database tables"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Get connection details from env
db_url = os.getenv("DATABASE_URL", "")
if "://" in db_url:
    db_url = db_url.split("://", 1)[1]

auth, location = db_url.split("@")
user, password = auth.split(":")
host_port, database = location.split("/")
if "?" in database:
    database = database.split("?")[0]
if ":" in host_port:
    host, port = host_port.split(":")
else:
    host, port = host_port, "5432"

# Connect and check tables
conn = psycopg2.connect(
    user=user,
    password=password,
    host=host,
    port=port,
    database=database
)

cur = conn.cursor()

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print("=" * 60)
print(f"📊 Database: {database}")
print("=" * 60)

required_tables = ['users', 'jobs', 'applications', 'user_skills', 'user_interactions']

if tables:
    print("\n✅ Tables found:")
    for table in tables:
        status = "✅" if table in required_tables else "ℹ️"
        print(f"   {status} {table}")
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"      └─ {count} rows")
else:
    print("\n❌ No tables found!")

# Check for missing required tables
missing = set(required_tables) - set(tables)
if missing:
    print(f"\n⚠️  Missing required tables: {', '.join(missing)}")
else:
    print("\n🎉 All required tables exist!")

cur.close()
conn.close()

print("=" * 60)
