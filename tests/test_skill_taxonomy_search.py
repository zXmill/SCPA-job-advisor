"""Regression tests for ESCO/O*NET-backed skill autocomplete."""

from __future__ import annotations

import httpx
import pytest


pytestmark = pytest.mark.anyio


async def _names(client: httpx.AsyncClient, query: str) -> list[str]:
    response = await client.get("/api/skills/search", params={"q": query, "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert all("source" in item and "confidence" in item for item in payload["skills"])
    return [item["name"] for item in payload["skills"]]


async def test_skill_search_returns_realistic_suggestions_for_short_and_domain_queries(
    client: httpx.AsyncClient,
) -> None:
    s_names = await _names(client, "s")
    machine_names = await _names(client, "machine")
    data_names = await _names(client, "data")
    credit_names = await _names(client, "credit")

    assert len(s_names) >= 5
    assert "SQL" in s_names
    assert "Machine Learning" in machine_names
    assert {"Data Analysis", "Data Science", "Data Engineering"} & set(data_names)
    assert "Credit Scoring" in credit_names


async def test_skill_search_supports_tool_language_and_indonesian_alias_queries(
    client: httpx.AsyncClient,
) -> None:
    assert "Docker" in await _names(client, "docker")
    assert "Kubernetes" in await _names(client, "kubernetes")
    assert "English" in await _names(client, "english")
    assert "Communication" in await _names(client, "komunikasi")
    assert "Data Analysis" in await _names(client, "analisis")
    assert "Machine Learning" in await _names(client, "ml")


async def test_skill_search_filters_obscure_software_products_from_user_facing_results(
    client: httpx.AsyncClient,
) -> None:
    names = await _names(client, "ai")

    assert "AI Agent" in names
    assert "Artificial Intelligence" in names
    assert "AI Squared ZoomText" not in names
