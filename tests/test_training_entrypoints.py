"""Smoke tests for local ML training and tuning entrypoints."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from services.hybrid.tuning.tune_weights import ndcg_at_k, tune_weights
from services.sbert.training.train_sbert import build_training_pairs, load_jsonl


def test_sbert_training_pair_builder(tmp_path: Path) -> None:
    data_path = tmp_path / "jobs.jsonl"
    data_path.write_text(
        "\n".join(
            [
                json.dumps({"title": "ML Engineer", "description": "Build models"}),
                json.dumps({"title": "", "description": "Missing title"}),
                json.dumps({"title": "Backend", "description": ""}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_jsonl(data_path)
    pairs = build_training_pairs(records)

    assert pairs == [("ML Engineer", "Build models")]


def test_ncf_training_cli_writes_checkpoint(tmp_path: Path) -> None:
    output_dir = tmp_path / "ncf"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.ncf.training.train_ncf",
            "--output-dir",
            str(output_dir),
            "--steps",
            "1",
            "--batch-size",
            "8",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["steps"] == 1
    assert (output_dir / "ncf_model.pt").exists()


def test_dqn_training_cli_writes_checkpoint(tmp_path: Path) -> None:
    output_dir = tmp_path / "dqn"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.dqn.training.train_dqn",
            "--output-dir",
            str(output_dir),
            "--steps",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["steps"] == 1
    assert payload["policy_objective"] == "skill_path"
    assert payload["mdp"]["state"] == "user_profile + missing_skills + market_demand"
    assert payload["mdp"]["action"] == "next_skill_course_certificate_or_career_milestone"
    assert payload["mdp"]["reward"] == "skill_gap_reduction + job_match_lift"
    assert payload["validation_reward"] >= payload["random_reward"]
    assert (output_dir / "dqn_model.pt").exists()


def test_hybrid_weight_tuning_returns_normalized_weights() -> None:
    sessions = [
        {
            "ncf_scores": [0.9, 0.1, 0.2],
            "sbert_scores": [0.8, 0.4, 0.3],
            "dqn_scores": [0.7, 0.2, 0.1],
            "applied_ids": [0],
        },
        {
            "ncf_scores": [0.2, 0.8, 0.1],
            "sbert_scores": [0.3, 0.7, 0.2],
            "dqn_scores": [0.1, 0.9, 0.2],
            "applied_ids": [1],
        },
    ]

    result = tune_weights(sessions)
    total = result["alpha_ncf"] + result["beta_sbert"] + result["gamma_dqn"]

    assert total == pytest.approx(1.0)
    assert result["validation_ndcg"] >= 0.0
    assert ndcg_at_k([0, 1, 2], {0}, k=3) == pytest.approx(1.0)
