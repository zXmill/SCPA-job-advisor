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
from scripts.eval.evaluate_finetuned_sbert import evaluate_finetuned_sbert


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


class TestEvaluateFinetunedSBERT:
    async def test_evaluate_finetuned_sbert_runs_and_produces_report(self, tmp_path: Path) -> None:
        from services.sbert.training.fine_tune_sbert import fine_tune_sbert

        data_path = tmp_path / "indonesian_pairs.jsonl"
        # Minimal dataset: 2 profiles with 1 positive + hard negative each
        synthetic = [
            {
                "profile_id": "u-ti-01",
                "job_id": "job-backend-001",
                "profile_text": "Teknik Informatika Python FastAPI PostgreSQL Docker",
                "job_text": "Backend Developer PT Teknologi Nusantara Jakarta Develop REST API microservices using Python FastAPI PostgreSQL Docker redis api",
                "hard_negative_text": "Master of Ceremony PT Event Nusantara Jakarta Host corporate events moderate panel discussions english event hosting public speaking communication",
                "profile_skills": ["python", "fastapi", "postgresql", "docker"],
                "job_skills": ["python", "fastapi", "postgresql", "docker", "api"],
                "label": 1.0,
                "pair_kind": "positive",
            },
            {
                "profile_id": "u-sasing-01",
                "job_id": "job-mc-001",
                "profile_text": "Sastra Inggris English public speaking content writing event host",
                "job_text": "Master of Ceremony PT Event Nusantara Jakarta Host corporate events moderate panel discussions english event hosting public speaking communication",
                "hard_negative_text": "Backend Developer PT Teknologi Nusantara Jakarta Develop REST API microservices using Python FastAPI PostgreSQL Docker redis api",
                "profile_skills": ["english", "public speaking", "content writing", "event hosting"],
                "job_skills": ["english", "event hosting", "public speaking", "communication"],
                "label": 1.0,
                "pair_kind": "positive",
            },
            {
                "profile_id": "u-ti-01",
                "job_id": "job-mc-001",
                "profile_text": "Teknik Informatika Python FastAPI PostgreSQL Docker",
                "job_text": "Master of Ceremony PT Event Nusantara Jakarta Host corporate events moderate panel discussions english event hosting public speaking communication",
                "profile_skills": ["python", "fastapi", "postgresql", "docker"],
                "job_skills": ["english", "event hosting", "public speaking", "communication"],
                "label": 0.0,
                "pair_kind": "negative",
            },
            {
                "profile_id": "u-sasing-01",
                "job_id": "job-backend-001",
                "profile_text": "Sastra Inggris English public speaking content writing event host",
                "job_text": "Backend Developer PT Teknologi Nusantara Jakarta Develop REST API microservices using Python FastAPI PostgreSQL Docker redis api",
                "profile_skills": ["english", "public speaking", "content writing", "event hosting"],
                "job_skills": ["python", "fastapi", "postgresql", "docker", "api"],
                "label": 0.0,
                "pair_kind": "negative",
            },
        ]
        data_path.write_text("\n".join(json.dumps(r) for r in synthetic) + "\n", encoding="utf-8")

        model_dir = tmp_path / "finetuned_test"
        # Quick fine-tune for smoke test
        fine_tune_sbert(
            data_path,
            model_dir,
            base_model="paraphrase-multilingual-MiniLM-L12-v2",
            epochs=1,
            batch_size=2,
        )

        output_dir = tmp_path / "finetuned_sbert_eval"
        report = evaluate_finetuned_sbert(
            data_path,
            model_dir,
            output_dir,
            k_values=(2,),
        )
        assert report["n_profiles"] == 2
        assert "recall_at_2" in report
        assert "mrr_at_2" in report
        assert "ndcg_at_2" in report
        assert "skill_gap_examples_count" in report
        assert (output_dir / "finetuned_sbert_full_report.json").exists()
        assert (output_dir / "skill_gap_examples.json").exists()
