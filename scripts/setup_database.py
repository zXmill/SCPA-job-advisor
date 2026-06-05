#!/usr/bin/env python3
"""Database Setup and Verification Script for SCPA

This script helps you:
1. Test PostgreSQL connection
2. Create database if it doesn't exist
3. Run migrations
4. Verify table creation

Usage:
    python scripts/setup_database.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv


def load_environment():
    """Load environment variables from .env file."""
    env_path = project_root / ".env"
    if not env_path.exists():
        print("❌ .env file not found!")
        print(f"   Expected location: {env_path}")
        print("\n   Please copy .env.example to .env and configure it.")
        sys.exit(1)
    
    load_dotenv(env_path)
    print("✅ Loaded environment variables from .env")


def parse_database_url():
    """Parse DATABASE_URL into connection components."""
    db_url = os.getenv("DATABASE_URL", "")
    
    if not db_url:
        print("❌ DATABASE_URL not found in .env file")
        sys.exit(1)
    
    # Remove protocol prefix
    if "://" in db_url:
        db_url = db_url.split("://", 1)[1]
    
    # Parse: user:password@host:port/database
    try:
        auth, location = db_url.split("@")
        user, password = auth.split(":")
        host_port, database = location.split("/")
        
        if "?" in database:
            database = database.split("?")[0]
        
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host, port = host_port, "5432"
        
        return {
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "database": database,
        }
    except Exception as e:
        print(f"❌ Failed to parse DATABASE_URL: {e}")
        print(f"   URL format: postgresql://user:password@host:port/database")
        sys.exit(1)


def test_connection(config, database="postgres"):
    """Test PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            user=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database=database,
        )
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        return False, str(e)


def create_database_if_not_exists(config):
    """Create database if it doesn't exist."""
    target_db = config["database"]
    
    # Connect to default 'postgres' database
    try:
        conn = psycopg2.connect(
            user=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (target_db,)
        )
        exists = cursor.fetchone()
        
        if exists:
            print(f"✅ Database '{target_db}' already exists")
        else:
            print(f"📦 Creating database '{target_db}'...")
            cursor.execute(f'CREATE DATABASE "{target_db}"')
            print(f"✅ Database '{target_db}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        return False


def verify_tables(config):
    """Verify that all required tables exist."""
    required_tables = [
        "users",
        "jobs",
        "applications",
        "user_skills",
        "user_interactions",
    ]
    
    try:
        conn = psycopg2.connect(
            user=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database=config["database"],
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print("\n📊 Database Tables:")
        for table in required_tables:
            if table in existing_tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} (missing)")
        
        cursor.close()
        conn.close()
        
        missing = set(required_tables) - set(existing_tables)
        return len(missing) == 0, missing
        
    except Exception as e:
        print(f"❌ Failed to verify tables: {e}")
        return False, []


def run_migrations():
    """Run Alembic migrations."""
    print("\n🔄 Running database migrations...")
    import subprocess
    
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            print("✅ Migrations completed successfully")
            print(result.stdout)
            return True
        else:
            print("❌ Migration failed:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ Alembic not found. Install it with: pip install alembic")
        return False


def main():
    """Main setup workflow."""
    print("=" * 60)
    print("SCPA Database Setup & Verification")
    print("=" * 60)
    
    # Step 1: Load environment
    print("\n[1/5] Loading environment configuration...")
    load_environment()
    
    # Step 2: Parse database URL
    print("\n[2/5] Parsing database connection...")
    config = parse_database_url()
    print(f"   Host: {config['host']}:{config['port']}")
    print(f"   User: {config['user']}")
    print(f"   Database: {config['database']}")
    
    # Step 3: Test connection
    print("\n[3/5] Testing PostgreSQL connection...")
    result = test_connection(config)
    if result is True:
        print("✅ Connection successful")
    else:
        print(f"❌ Connection failed: {result[1]}")
        print("\n   Troubleshooting:")
        print("   - Is PostgreSQL running?")
        print("   - Is the password correct in .env?")
        print("   - Is port 5432 accessible?")
        sys.exit(1)
    
    # Step 4: Create database
    print("\n[4/5] Checking database existence...")
    if not create_database_if_not_exists(config):
        sys.exit(1)
    
    # Step 5: Verify tables
    print("\n[5/5] Verifying database schema...")
    tables_ok, missing = verify_tables(config)
    
    if not tables_ok:
        print(f"\n⚠️  Missing tables: {', '.join(missing)}")
        response = input("\nRun migrations to create tables? (y/n): ")
        
        if response.lower() == 'y':
            if run_migrations():
                print("\n✅ Verifying tables after migration...")
                tables_ok, _ = verify_tables(config)
                if tables_ok:
                    print("\n🎉 Database setup complete!")
                else:
                    print("\n⚠️  Some tables are still missing. Check migration logs.")
            else:
                print("\n❌ Migration failed. Check the error messages above.")
        else:
            print("\n⚠️  Skipping migrations. Run manually with: alembic upgrade head")
    else:
        print("\n🎉 All tables exist! Database is ready.")
    
    print("\n" + "=" * 60)
    print("Next steps:")
    print("  1. Start services: docker-compose up -d")
    print("  2. Check health: curl http://localhost:8000/health")
    print("  3. View logs: docker-compose logs -f")
    print("=" * 60)


if __name__ == "__main__":
    main()
