"""SCPA backend test fixtures.

Provides:
    - A bootstrapped ``db_scpa_test`` PostgreSQL database (created via
      ``scripts/_ensure_test_db.py`` before this conftest is imported).
    - Schema applied via ``Base.metadata.create_all`` on first use.
    - Per-test TRUNCATE so each test starts from a clean slate without
      paying the schema recreate cost.
    - A gateway FastAPI app whose module-level engine, session factory,
      and ``httpx`` client are wired to the test database.
    - An async HTTP client driven by ``httpx.ASGITransport`` so tests
      exercise the real route handlers, dependency graph, and Pydantic
      validation — not a stub.

The fixtures intentionally avoid running the gateway's production
lifespan because the gateway constructs its own engine at startup
against ``DATABASE_URL``. We swap in the test engine before any
request and tear it down after the session ends.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncIterator

import pytest

# Ensure repo root is on sys.path so ``services.gateway.main`` resolves
# without requiring ``pip install -e .``
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Force JWT_SECRET to a known deterministic value BEFORE the gateway
# module is imported so token generation is stable across the run.
os.environ["JWT_SECRET"] = "test-secret-32-bytes-long-key!!!"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-32-bytes-key!!"
os.environ.setdefault("SBERT_FORCE_FALLBACK", "1")
# Disable the production catalog freshness ceiling for the suite: many tests
# insert jobs at fixed ages (e.g. 80/90 days) to assert filter behavior, and
# those should not be silently hidden. Tests that exercise the ceiling set it
# explicitly via monkeypatch.
os.environ.setdefault("JOB_CATALOG_MAX_AGE_DAYS", "0")

# Point the gateway at the test database BEFORE import. The gateway
# reads ``DATABASE_URL`` at module load time.
_TEST_DB_NAME = os.environ.get("SCPA_TEST_DB", "db_scpa_test")
_PG_USER = os.environ.get("POSTGRES_USER", "postgres")
_PG_PWD = os.environ.get("POSTGRES_PASSWORD", "AdminPass456")
_PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PWD}"
    f"@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


import httpx  # noqa: E402  (must come after env setup)
from httpx import ASGITransport  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.models import Base  # noqa: E402
import services.gateway.main as gateway_module  # noqa: E402


# ════════════════════════════════════════════════════════════════
# anyio backend — constrain to asyncio (matches existing test style)
# ════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run async tests on asyncio only (not trio).

    Must be session-scoped so async session-scoped fixtures (e.g.
    ``_bootstrapped_engine``) can depend on it without raising
    ``ScopeMismatch``.
    """
    return "asyncio"


# ════════════════════════════════════════════════════════════════
# Database engine + schema
# ════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Expose the resolved test DB URL for diagnostics."""
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def _table_names() -> list[str]:
    """Tables we know about — used by TRUNCATE between tests."""
    return [
        "hybrid_request_log",
        "hybrid_weights",
        "model_feedback_outbox",
        "dqn_replay_archive",
        "dqn_session_logs",
        "job_alerts",
        "skill_gap_snapshots",
        "experiment_metrics",
        "experiment_assignments",
        "experiments",
        "feedback_events",
        "served_slate_items",
        "served_slates",
        "user_job_interactions",
        "user_interactions",
        "applications",
        "user_certifications",
        "job_required_skills",
        "certification_skills",
        "user_skills",
        "skills",
        "jobs",
        "users",
    ]


@pytest.fixture(scope="session")
async def _bootstrapped_engine():
    """Create the test engine once per session and apply schema.

    Drops all tables and ENUM types at the end of the session so a
    repeated run starts clean.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        # Force UTF-8 client encoding and English error messages.
        # The local Postgres install is on Indonesian Windows locale,
        # which otherwise produces mojibake in DDL error responses
        # (e.g. "nilai masukan tidak valid" with mangled string literals).
        connect_args={
            "server_settings": {
                "client_encoding": "utf8",
                "lc_messages": "C",
            }
        },
    )

    # Apply schema. The ORM models declare ``Enum(UserRole, ...)`` etc.
    # which, with default SQLAlchemy behaviour, would emit the enum's
    # Python attribute names ("USER", "ADMIN", ...) as the stored
    # labels. The production migration and the gateway code, however,
    # use the lowercase enum *values* ("user", "admin", ...). To keep
    # tests faithful to production we:
    #   1. drop all tables (start clean)
    #   2. drop and re-create the 8 enum types with the correct
    #      lowercase value labels
    #   3. run create_all(checkfirst=True) so SQLAlchemy creates only
    #      the tables and reuses the pre-existing enums
    enum_value_map = {
        "userrole": ("user", "admin", "premium"),
        "jobtype": ("full_time", "part_time", "contract", "internship"),
        "employmentmode": ("onsite", "remote", "hybrid"),
        "experiencelevel": ("entry", "mid", "senior"),
        "jobsource": (
            "jobstreet", "linkedin", "glints", "kalibrr", "karir",
            "topkarir", "kitalulus", "techinasia", "remotive", "indeed",
        ),
        "applicationstatus": (
            "submitted", "reviewed", "accepted", "rejected", "withdrawn"
        ),
        "skillcategory": ("technical", "soft", "linguistic"),
        "proficiencylevel": ("beginner", "intermediate", "advanced"),
    }

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        for enum_name in enum_value_map:
            await conn.execute(
                text(f"DROP TYPE IF EXISTS {enum_name} CASCADE")
            )
        for enum_name, labels in enum_value_map.items():
            quoted = ", ".join(f"'{label}'" for label in labels)
            await conn.execute(
                text(f"CREATE TYPE {enum_name} AS ENUM ({quoted})")
            )
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, checkfirst=True
            )
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_engine(_bootstrapped_engine, _table_names):
    """Per-test fixture: ensure tables are empty before the test runs.

    Truncating is dramatically faster than drop+create and preserves
    indexes and ENUMs across the session. ``RESTART IDENTITY CASCADE``
    resets BigInteger sequences used by ``user_skills`` and
    ``user_interactions``.
    """
    async with _bootstrapped_engine.begin() as conn:
        joined = ", ".join(_table_names)
        await conn.execute(
            text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")
        )
    return _bootstrapped_engine


@pytest.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """A direct AsyncSession for tests that need to inspect DB state.

    The session is independent of the one the gateway uses for its
    request handling; both bind to the same test engine.
    """
    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


# ════════════════════════════════════════════════════════════════
# Gateway app wiring
# ════════════════════════════════════════════════════════════════

@pytest.fixture
async def gateway_app(db_engine):
    """Yield the real gateway FastAPI app wired to the test engine.

    The gateway's module-level ``engine``, ``SessionLocal``, and
    ``http_client`` are normally initialised in the ``lifespan``
    handler. Since ``ASGITransport`` does not run lifespan events by
    default, we initialise those globals here and restore them
    afterwards.
    """
    test_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    prior_engine = gateway_module.engine
    prior_factory = gateway_module.SessionLocal
    prior_http = gateway_module.http_client

    gateway_module.engine = db_engine
    gateway_module.SessionLocal = test_factory
    gateway_module.http_client = httpx.AsyncClient(timeout=5.0)

    try:
        yield gateway_module.app
    finally:
        await gateway_module.http_client.aclose()
        gateway_module.engine = prior_engine
        gateway_module.SessionLocal = prior_factory
        gateway_module.http_client = prior_http


@pytest.fixture
async def client(gateway_app) -> AsyncIterator[httpx.AsyncClient]:
    """An async HTTP client that drives the gateway via ASGI in-process."""
    transport = ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac
