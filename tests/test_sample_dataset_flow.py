"""Permanent sample dataset training and evaluation tests."""

from __future__ import annotations

from pathlib import Path

from scripts.evaluate_sample_pipeline import evaluate
from scripts.retrain_models import run_retraining
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR, load_sample_dataset, validate_sample_dataset


def test_sample_dataset_is_valid_and_complete() -> None:
    dataset = load_sample_dataset(DEFAULT_SAMPLE_DIR)
    assert validate_sample_dataset(dataset) == []
    assert len(dataset["users"]) >= 5
    assert len(dataset["jobs"]) >= 8
    assert len(dataset["interactions"]) >= 20
    assert len(dataset["milestones"]) >= 5

    for job in dataset["jobs"]:
        assert job["title"]
        assert job["company"]
        assert job["location"]
        assert job["source_url"]
        assert job["description"]
        assert job["skills"]
        assert job["company_logo"]


def test_sample_dataset_evaluation_meets_pdf_targets() -> None:
    result = evaluate(load_sample_dataset(DEFAULT_SAMPLE_DIR))

    assert result["ready"] is True
    assert result["metrics"]["top5_accuracy"] >= 0.85
    assert result["metrics"]["ndcg_at_5"] >= 0.85
    assert result["metrics"]["ctr_proxy"] >= 0.25
    assert result["metrics"]["latency_p95_ms"] < 1000
    assert result["metrics"]["fairness_gap_pp"] < 8
    assert result["metrics"]["dqn_action_accuracy"] >= 0.8
    assert result["ablation"]["full_ndcg_at_5"] > result["ablation"]["sbert_only_ndcg_at_5"]


def test_retraining_flow_writes_artifacts_and_keeps_fallbacks(tmp_path: Path) -> None:
    result = run_retraining(DEFAULT_SAMPLE_DIR, tmp_path / "retrain", steps=1)

    assert result["status"] == "ok"
    assert result["evaluation"]["ready"] is True
    for model_name in ("sbert", "ncf", "dqn"):
        model = result["models"][model_name]
        assert model["status"] == "trained"
        assert Path(model["checkpoint"]).exists()
    assert Path(result["manifest"]).exists()

