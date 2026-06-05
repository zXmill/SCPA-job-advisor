"""Tests for CV/resume upload endpoint."""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.anyio, pytest.mark.db]

DEFAULT_PASSWORD = "Str0ng-Pass!word"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(
    client,
    *,
    email: str = "cv-user@example.com",
    name: str = "CV User",
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _insert_skills(db_session: AsyncSession) -> None:
    """Seed skills into the taxonomy so CV extraction has something to match."""
    skills = [
        ("Python", "technical", ["python", "py"]),
        ("SQL", "technical", ["sql"]),
        ("Docker", "technical", ["docker"]),
        ("Kubernetes", "technical", ["kubernetes", "k8s"]),
    ]
    for name, category, aliases in skills:
        await db_session.execute(
            text(
                "INSERT INTO skills (name, category, aliases) "
                "VALUES (:name, :category, :aliases) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"name": name, "category": category, "aliases": aliases},
        )
    await db_session.commit()


async def test_cv_upload_txt_extracts_skills(client, db_session) -> None:
    """Upload a plain-text CV with known skills; assert canonical skills are extracted."""
    await _insert_skills(db_session)
    reg = await _register(client)
    cv_text = (
        "Budi Santoso\n"
        "Software Engineer with 5 years of experience.\n"
        "Skills: Python, SQL, Docker, Kubernetes.\n"
    )
    response = await client.post(
        "/api/profile/cv",
        headers=_auth_header(reg["access_token"]),
        files={"file": ("cv_budi.txt", cv_text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["extracted_skills"]) > 0
    assert data["filename"] == "cv_budi.txt"
    assert "uploaded_at" in data


async def test_cv_upload_unsupported_type(client) -> None:
    """Upload an unsupported file type; assert 400."""
    reg = await _register(client)
    response = await client.post(
        "/api/profile/cv",
        headers=_auth_header(reg["access_token"]),
        files={"file": ("cv_budi.png", b"fake image", "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


async def test_cv_upload_empty_file(client) -> None:
    """Upload an empty file; assert 400."""
    reg = await _register(client)
    response = await client.post(
        "/api/profile/cv",
        headers=_auth_header(reg["access_token"]),
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


async def test_cv_upload_no_auth(client) -> None:
    """Request without auth; assert 401."""
    response = await client.post(
        "/api/profile/cv",
        files={"file": ("cv.txt", b"some text", "text/plain")},
    )
    assert response.status_code == 401
