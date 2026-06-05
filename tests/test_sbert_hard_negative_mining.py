"""Contracts for deterministic SBERT hard-negative mining."""

from __future__ import annotations

import json
from pathlib import Path

from services.sbert.training.hard_negatives import (
    mine_hard_negative_examples,
    validate_positive_outranks_negatives,
)
from services.sbert.training.train_sbert import (
    build_hard_negative_training_examples,
    train_from_records,
)


def _same_sector_records() -> list[dict[str, object]]:
    return [
        {
            "id": "backend-python",
            "query": "Python backend API developer",
            "positive": "Backend Engineer building Python FastAPI PostgreSQL REST APIs",
            "sector": "technology",
            "required_skills": ["python", "fastapi", "postgresql", "api"],
        },
        {
            "id": "frontend-react",
            "query": "React frontend interface developer",
            "positive": "Frontend Engineer building React TypeScript UI components",
            "sector": "technology",
            "required_skills": ["react", "typescript", "ui"],
        },
        {
            "id": "ml-pytorch",
            "query": "Machine learning model deployment",
            "positive": "ML Engineer deploying PyTorch recommendation models and feature pipelines",
            "sector": "technology",
            "required_skills": ["pytorch", "machine learning", "model deployment"],
        },
        {
            "id": "cloud-kubernetes",
            "query": "Cloud infrastructure Kubernetes",
            "positive": "DevOps Engineer managing Docker and Kubernetes clusters",
            "sector": "technology",
            "required_skills": ["docker", "kubernetes", "cloud"],
        },
    ]


def test_sbert_hard_negative_mining_is_deterministic_same_sector_wrong_skill() -> None:
    records = _same_sector_records()

    first = [example.to_training_row() for example in mine_hard_negative_examples(records)]
    second = [example.to_training_row() for example in mine_hard_negative_examples(list(reversed(records)))]

    assert first == second
    assert {row["sector"] for row in first} == {"technology"}
    assert len(first) == len(records)
    for row in first:
        assert row["positive"] != row["hard_negative"]
        assert set(row["positive_skills"]).isdisjoint(row["negative_skills"])


def test_sbert_hard_negative_contract_positive_scores_outrank_negatives() -> None:
    examples = mine_hard_negative_examples(_same_sector_records())

    metrics = validate_positive_outranks_negatives(examples)

    assert metrics["hard_negative_pairs"] == len(_same_sector_records())
    assert metrics["ranking_violations"] == 0
    assert metrics["positive_outrank_rate"] == 1.0
    for example in examples:
        assert example.positive_score > example.negative_score
        assert example.margin > 0.0


def test_sbert_training_entrypoint_writes_hard_negative_contract(tmp_path: Path) -> None:
    rows = build_hard_negative_training_examples(_same_sector_records())

    metrics = train_from_records(_same_sector_records(), tmp_path, steps=1)
    hard_negative_path = tmp_path / "hard_negatives.jsonl"
    persisted_rows = [
        json.loads(line)
        for line in hard_negative_path.read_text(encoding="utf-8").splitlines()
    ]

    assert metrics["negative_source"] == "hard_negative"
    assert metrics["hard_negative_contract"] == "same-sector-wrong-skill"
    assert metrics["hard_negative_pairs"] == len(rows)
    assert persisted_rows == rows
