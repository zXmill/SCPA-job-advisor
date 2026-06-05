"""Tests for deterministic database seed/backfill contracts."""

from __future__ import annotations

import importlib


def test_seed_module_import_does_not_require_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    seed = importlib.import_module("db.seed")

    cleanup_order = seed.get_database_cleanup_order()
    assert cleanup_order.index("feedback_events") < cleanup_order.index("served_slate_items")
    assert cleanup_order.index("served_slate_items") < cleanup_order.index("served_slates")
    assert cleanup_order.index("served_slates") < cleanup_order.index("users")


def test_recommendation_evidence_seed_rows_cover_database_contracts(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    seed = importlib.import_module("db.seed")

    rows = seed.build_recommendation_evidence_seed_rows(
        users=[{"id": "00000000-0000-0000-0000-000000000001"}],
        jobs=[
            {"id": "00000000-0000-0000-0000-000000000101"},
            {"id": "00000000-0000-0000-0000-000000000102"},
        ],
    )

    assert set(rows) == {
        "served_slates",
        "served_slate_items",
        "feedback_events",
        "model_artifacts",
        "embedding_cache_entries",
        "model_entity_mappings",
        "dqn_episodes",
    }
    assert rows["served_slates"][0]["model_versions"] == {
        "sbert": "sbert-seed-v1",
        "ncf": "ncf-seed-v1",
        "dqn": "dqn-seed-v1",
    }
    assert {event["event_type"] for event in rows["feedback_events"]} >= {
        "impression",
        "view",
        "save",
    }
    assert all(not artifact["fallback_mode"] for artifact in rows["model_artifacts"])
