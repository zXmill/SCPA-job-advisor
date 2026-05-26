"""Smoke tests for ML inventory and training plan docs (P5-ML-001)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.anyio]


class TestMLInventoryDoc:
    def test_ml_inventory_doc_exists(self) -> None:
        path = Path("docs/ml/ML_INVENTORY.md")
        assert path.exists(), f"{path} does not exist"

    def test_ml_inventory_doc_has_content(self) -> None:
        path = Path("docs/ml/ML_INVENTORY.md")
        text = path.read_text(encoding="utf-8")
        assert len(text) > 5000, "ML inventory doc is too short"
        assert "SBERT" in text
        assert "NCF" in text
        assert "DQN" in text
        assert "Calibration" in text

    def test_ml_inventory_has_hyperparameters(self) -> None:
        path = Path("docs/ml/ML_INVENTORY.md")
        text = path.read_text(encoding="utf-8")
        assert "Embedding dim" in text
        assert "Learning rate" in text
        assert "Gamma" in text

    def test_ml_inventory_has_entry_points(self) -> None:
        path = Path("docs/ml/ML_INVENTORY.md")
        text = path.read_text(encoding="utf-8")
        assert "Training Entry Point" in text
        assert "Evaluation Entry Point" in text


class TestTrainingPlanDoc:
    def test_training_plan_doc_exists(self) -> None:
        path = Path("docs/ml/TRAINING_PLAN.md")
        assert path.exists(), f"{path} does not exist"

    def test_training_plan_doc_has_content(self) -> None:
        path = Path("docs/ml/TRAINING_PLAN.md")
        text = path.read_text(encoding="utf-8")
        assert len(text) > 5000, "Training plan doc is too short"
        assert "SBERT" in text
        assert "NCF" in text
        assert "DQN" in text
        assert "Calibration" in text

    def test_training_plan_has_schedules(self) -> None:
        path = Path("docs/ml/TRAINING_PLAN.md")
        text = path.read_text(encoding="utf-8")
        assert "Retraining Schedule" in text
        assert "Validation" in text

    def test_training_plan_has_targets(self) -> None:
        path = Path("docs/ml/TRAINING_PLAN.md")
        text = path.read_text(encoding="utf-8")
        assert "NDCG@5" in text
        assert "Precision@5" in text
