"""Tests for model evaluation scripts (P5-ML-002 through P5-ML-005).

Validates that each evaluation script runs successfully and produces
expected output files and metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.evaluate_sbert import evaluate_sbert
from scripts.eval.evaluate_ncf import evaluate_ncf
from scripts.eval.evaluate_dqn import evaluate_dqn
from scripts.eval.evaluate_calibrator import evaluate_calibrator


pytestmark = [pytest.mark.anyio]


class TestEvaluateSBERT:
    async def test_evaluate_sbert_runs_and_produces_report(self, tmp_path: Path) -> None:
        data_path = tmp_path / "test_pairs.jsonl"
        synthetic = [
            {"profile_text": "Sastra Inggris", "job_text": "Master of Ceremony", "pair_kind": "positive"},
            {"profile_text": "Sastra Inggris", "job_text": "Backend Developer", "pair_kind": "negative"},
            {"profile_text": "Computer Science", "job_text": "Backend Developer", "pair_kind": "positive"},
            {"profile_text": "Computer Science", "job_text": "Master of Ceremony", "pair_kind": "negative"},
        ]
        data_path.write_text("\n".join(json.dumps(r) for r in synthetic) + "\n", encoding="utf-8")
        output_dir = tmp_path / "sbert_eval"
        report = evaluate_sbert(data_path, output_dir, k_values=(5,))
        assert report["n_queries"] == 2
        assert "precision_at_5" in report
        assert "ndcg_at_5" in report
        assert (output_dir / "sbert_evaluation.json").exists()


class TestEvaluateNCF:
    async def test_evaluate_ncf_runs_and_produces_report(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ncf_eval"
        report = evaluate_ncf(
            output_dir, num_users=16, num_items=32, steps=20, batch_size=16, k_values=(5,)
        )
        assert report["n_queries"] > 0
        assert "precision_at_5" in report
        assert "ndcg_at_5" in report
        assert (output_dir / "ncf_evaluation.json").exists()


class TestEvaluateDQN:
    async def test_evaluate_dqn_runs_and_produces_report(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "dqn_eval"
        report = evaluate_dqn(output_dir, training_steps=20, k_values=(2,))
        assert report["n_queries"] == 3
        assert "policy_accuracy" in report
        assert report["policy_accuracy"] >= 0.5  # Should beat random at least sometimes
        assert (output_dir / "dqn_evaluation.json").exists()


class TestEvaluateCalibrator:
    async def test_evaluate_calibrator_runs_and_produces_report(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "calib_eval"
        report = evaluate_calibrator(output_dir, k_values=(3,))
        assert report["n_queries"] > 0
        assert "calibrated_ndcg_at_3" in report
        assert "static_ndcg_at_3" in report
        assert "ndcg_lift_at_3" in report
        assert "feature_importance" in report
        assert (output_dir / "calibrator_evaluation.json").exists()
