"""Backend contract tests for the profile completeness summary."""

from __future__ import annotations

from typing import Any

import pytest


pytestmark = [pytest.mark.anyio, pytest.mark.db]


DEFAULT_PASSWORD = "Str0ng-Pass!word"


async def _register(
    client,
    *,
    name: str = "Ibnu Test",
    email: str = "ibnu-profile@example.com",
    password: str = DEFAULT_PASSWORD,
) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_profile_completeness_requires_auth(client) -> None:
    response = await client.get("/api/profile/completeness")

    assert response.status_code == 401


async def test_profile_completeness_reports_missing_profile_items(client) -> None:
    registration = await _register(client)

    response = await client.get(
        "/api/profile/completeness",
        headers=_auth_header(registration["access_token"]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["percent"] == 20
    assert body["completed_item_ids"] == ["name"]
    assert body["missing_item_ids"] == ["program_studi", "university", "skills", "cv"]
    assert body["stored_percent"] == 10
    assert body["skill_count"] == 0
    items = {item["id"]: item for item in body["items"]}
    assert items["name"] == {
        "id": "name",
        "label": "Nama lengkap",
        "completed": True,
    }
    assert items["skills"] == {
        "id": "skills",
        "label": "Keahlian",
        "completed": False,
    }
    assert items["cv"] == {
        "id": "cv",
        "label": "CV/Resume",
        "completed": False,
    }


async def test_profile_completeness_reaches_100_after_profile_and_cv(client) -> None:
    registration = await _register(client)
    headers = _auth_header(registration["access_token"])

    update = await client.put(
        "/api/profile",
        json={
            "program_studi": "Teknik Informatika",
            "university": "Universitas Bina Sarana Informatika",
            "skills": ["Python", "SQL"],
        },
        headers=headers,
    )
    assert update.status_code == 200, update.text

    response = await client.get("/api/profile/completeness", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["percent"] == 80
    assert body["completed_item_ids"] == [
        "name",
        "program_studi",
        "university",
        "skills",
    ]
    assert body["missing_item_ids"] == ["cv"]
    assert body["skill_count"] == 2
    assert not all(item["completed"] for item in body["items"])

    upload = await client.post(
        "/api/profile/cv",
        files={"file": ("cv.txt", b"Python SQL", "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text

    completed = await client.get("/api/profile/completeness", headers=headers)
    assert completed.status_code == 200, completed.text
    completed_body = completed.json()
    assert completed_body["percent"] == 100
    assert completed_body["missing_item_ids"] == []
    assert completed_body["completed_item_ids"] == [
        "name",
        "program_studi",
        "university",
        "skills",
        "cv",
    ]
    assert completed_body["cv_uploaded_at"]
    assert all(item["completed"] for item in completed_body["items"])
