"""Smoke-test the SCPA auth flow against the *real* db_scpa database.

Drives the actual gateway FastAPI app in-process via ``httpx.ASGITransport``
but bound to the real database (``DATABASE_URL`` from ``.env``), not the
test database. Prints a pass/fail summary for the key auth flows the
frontend depends on.

Run after ``alembic upgrade head`` and ``python -m db.seed``.

This is a smoke test, not a unit test — it is safe to run repeatedly
because it uses a unique randomly-suffixed test email so it never
conflicts with seeded users and never deletes existing data.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Ensure we import the gateway with .env values (real db_scpa)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()

import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import services.gateway.main as gateway_module


def _async_dsn() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}PASS{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}FAIL{RESET} {msg}")


def _masked_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.password:
        return url
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}" if username else f"***@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


async def main() -> int:
    print(f"{DIM}DATABASE_URL = {_masked_url(os.environ['DATABASE_URL'])}{RESET}")

    # Wire the gateway's globals to the real DB (skip lifespan)
    engine = create_async_engine(
        _async_dsn(), pool_pre_ping=True, pool_size=2
    )
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    gateway_module.engine = engine
    gateway_module.SessionLocal = factory
    gateway_module.http_client = httpx.AsyncClient(timeout=5.0)

    failures = 0

    async with httpx.AsyncClient(
        transport=ASGITransport(app=gateway_module.app),
        base_url="http://smoke",
    ) as client:
        # 1. Login as the seeded user
        print("\n[1/5] Login as seeded user budi@example.com")
        r = await client.post(
            "/api/auth/login",
            json={"email": "budi@example.com", "password": "password123"},
        )
        if r.status_code == 200 and "access_token" in r.json():
            ok("seeded user can log in")
            seeded_token = r.json()["access_token"]
            seeded_user_id = r.json()["user"]["id"]
        else:
            fail(f"seeded login: status={r.status_code} body={r.text}")
            failures += 1
            seeded_token = None

        # 2. /api/auth/me returns full profile + skills
        print("\n[2/5] GET /api/auth/me with seeded token")
        if seeded_token:
            r = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {seeded_token}"},
            )
            body = r.json() if r.status_code == 200 else {}
            if (
                r.status_code == 200
                and body.get("email") == "budi@example.com"
                and isinstance(body.get("skills"), list)
                and len(body["skills"]) >= 5
            ):
                ok(
                    f"/me returned profile with {len(body['skills'])} skills"
                )
            else:
                fail(f"/me: status={r.status_code} body={r.text}")
                failures += 1

        # 3. Register a NEW user (random suffix so we never collide)
        suffix = uuid.uuid4().hex[:8]
        new_email = f"smoke_{suffix}@example.com"
        new_password = "SmokeTest-Pass1!"
        print(f"\n[3/5] Register new user {new_email}")
        r = await client.post(
            "/api/auth/register",
            json={
                "name": f"Smoke Test {suffix}",
                "email": new_email,
                "password": new_password,
            },
        )
        if r.status_code == 200 and "access_token" in r.json():
            ok("register returned 200 with access_token")
            new_token = r.json()["access_token"]
            new_user_id = r.json()["user"]["id"]
        else:
            fail(f"register: status={r.status_code} body={r.text}")
            failures += 1
            new_token = None

        # 4. Fillout / onboarding flow for the new user
        if new_token:
            print(f"\n[4/5] Fillout onboarding for {new_email}")
            headers = {"Authorization": f"Bearer {new_token}"}
            steps_ok = True
            r = await client.put(
                "/api/profile/onboarding",
                json={
                    "step": 1,
                    "data": {
                        "program_studi": "Teknik Informatika",
                        "university": "Universitas Bina Sarana Informatika",
                    },
                },
                headers=headers,
            )
            steps_ok &= r.status_code == 200
            r = await client.put(
                "/api/profile/onboarding",
                json={
                    "step": 2,
                    "data": {"skills": ["Python", "FastAPI", "PostgreSQL"]},
                },
                headers=headers,
            )
            steps_ok &= r.status_code == 200
            r = await client.put(
                "/api/profile/onboarding",
                json={"step": 3, "data": {}},
                headers=headers,
            )
            steps_ok &= r.status_code == 200

            # Verify /me reflects the fillout
            r = await client.get("/api/auth/me", headers=headers)
            body = r.json()
            if (
                steps_ok
                and r.status_code == 200
                and body["program_studi"] == "Teknik Informatika"
                and body["completion_percent"] >= 85
                and {s["skill"] for s in body["skills"]} == {
                    "Python", "FastAPI", "PostgreSQL"
                }
            ):
                ok(
                    f"3-step onboarding completed "
                    f"(completion_percent={body['completion_percent']})"
                )
            else:
                fail(f"onboarding: steps_ok={steps_ok} body={body}")
                failures += 1

        # 5. Confirm the new user can log in with their password
        print(f"\n[5/5] Login as newly-registered user {new_email}")
        r = await client.post(
            "/api/auth/login",
            json={"email": new_email, "password": new_password},
        )
        if r.status_code == 200 and r.json()["user"]["email"] == new_email:
            ok("new user can log in with their password")
        else:
            fail(f"new-user login: status={r.status_code} body={r.text}")
            failures += 1

        # Cleanup: remove the smoke user so the DB stays tidy
        async with factory() as session:
            from sqlalchemy import text
            await session.execute(
                text("DELETE FROM users WHERE email = :e"),
                {"e": new_email},
            )
            await session.commit()
        print(f"{DIM}\nCleanup: removed smoke user {new_email}{RESET}")

    await gateway_module.http_client.aclose()
    await engine.dispose()

    print(f"\n{'='*60}")
    if failures == 0:
        print(f"{GREEN}SMOKE PASSED — auth flow works against real db_scpa{RESET}")
        return 0
    print(f"{RED}SMOKE FAILED — {failures} check(s) did not pass{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
