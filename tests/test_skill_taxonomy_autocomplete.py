"""Backend contracts for skill taxonomy autocomplete suggestions."""

from __future__ import annotations

import pytest


pytestmark = [pytest.mark.anyio, pytest.mark.db]


async def test_skill_autocomplete_can_exclude_selected_skills(client) -> None:
    response = await client.get(
        "/api/skills/search",
        params=[("q", "py"), ("exclude", "Python")],
    )

    assert response.status_code == 200
    names = [skill["name"] for skill in response.json()["skills"]]
    assert "Python" not in names


async def test_skill_autocomplete_exclude_accepts_alias_and_comma_list(client) -> None:
    response = await client.get(
        "/api/skills/search",
        params={"q": "p", "exclude": "py,sql", "limit": "20"},
    )

    assert response.status_code == 200
    names = {skill["name"] for skill in response.json()["skills"]}
    assert "Python" not in names
    assert "SQL" not in names
