"""Tests for generated ML readiness data and evaluation graphics."""

from __future__ import annotations

from pathlib import Path

import nbformat

from scripts.build_ml_readiness_notebook import write_notebook
from scripts.generate_ml_readiness_assets import TARGETS, generate_all


def test_readiness_generator_writes_service_training_data_and_figures(
    tmp_path: Path,
) -> None:
    result = generate_all(
        output_dir=tmp_path / "readiness",
        data_root=tmp_path / "services",
    )

    expected_services = {"pipeline", "sbert", "ncf", "dqn", "hybrid"}
    assert set(result["data"]) == expected_services
    for path in result["data"].values():
        assert path.exists()
        assert path.stat().st_size > 0

    expected_figures = {
        "readiness_matrix",
        "operational_matrix",
        "dqn_reward_vs_random",
        "alpha_tuning",
        "pipeline_quality",
    }
    assert set(result["figures"]) == expected_figures
    for path in result["figures"].values():
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000

    assert result["metrics_path"].exists()
    assert result["csv_path"].exists()
    assert result["report_path"].exists()


def test_readiness_metrics_meet_targets(tmp_path: Path) -> None:
    result = generate_all(
        output_dir=tmp_path / "readiness",
        data_root=tmp_path / "services",
    )
    metrics = result["metrics"]

    assert metrics["ready"] is True
    assert all(row["passed"] for row in metrics["readiness"])

    values = metrics["metrics"]
    assert values["top5_accuracy"] >= TARGETS["top5_accuracy"]["target"]
    assert values["ndcg_at_5"] >= TARGETS["ndcg_at_5"]["target"]
    assert values["ctr"] >= TARGETS["ctr"]["target"]
    assert values["sus"] >= TARGETS["sus"]["target"]
    assert values["p95_latency_ms"] <= TARGETS["p95_latency_ms"]["target"]
    assert values["fairness_gap_pp"] <= TARGETS["fairness_gap_pp"]["target"]
    assert values["cache_hit_rate"] >= TARGETS["cache_hit_rate"]["target"]
    assert values["dqn_reward_lift"] >= TARGETS["dqn_reward_lift"]["target"]

    assert metrics["pipeline"]["duplicate_job_ids_after_dedup"] == 0
    assert metrics["pipeline"]["verification_mismatches"] == 0
    assert (
        metrics["alpha_tuning"]["best_ndcg_at_5"]
        > metrics["alpha_tuning"]["uniform_alpha_ndcg_at_5"]
    )


def test_readiness_notebook_is_valid_and_links_requested_outputs(
    tmp_path: Path,
) -> None:
    notebook_path = write_notebook(tmp_path / "scpa_ml_readiness_evaluation.ipynb")
    notebook = nbformat.read(notebook_path, as_version=4)
    nbformat.validate(notebook)

    source = "\n".join(cell.source for cell in notebook.cells)
    assert "generate_all(output_dir=OUTPUT_DIR, data_root=DATA_ROOT)" in source
    assert "dqn_reward_vs_random" in source
    assert "alpha_tuning" in source
    assert "pipeline_quality" in source
    assert "assert metrics[\"ready\"] is True" in source
