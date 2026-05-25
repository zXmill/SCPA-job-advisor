"""CORS configuration tests for the gateway."""

from __future__ import annotations

import pytest

from services.gateway import main as gateway_module


def test_development_cors_defaults_to_localhost_origins() -> None:
    origins = gateway_module._resolve_cors_origins("development", None)

    assert origins == ["http://localhost:3000", "http://localhost:8000"]


def test_cors_origin_parser_strips_empty_items() -> None:
    origins = gateway_module._resolve_cors_origins(
        "development",
        " https://example.com, ,http://localhost:3000 ",
    )

    assert origins == ["https://example.com", "http://localhost:3000"]


def test_production_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(RuntimeError, match="Wildcard CORS origins"):
        gateway_module._resolve_cors_origins("production", "*")


def test_production_cors_requires_explicit_origins() -> None:
    with pytest.raises(RuntimeError, match="CORS origins must be configured"):
        gateway_module._resolve_cors_origins("production", "")
