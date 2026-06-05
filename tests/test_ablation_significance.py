"""Tests for ablation evaluation and statistical significance."""

from __future__ import annotations

import pytest

from services.evaluation.ablation import (
    ABLATION_VARIANTS,
    ablation_summary_table,
    evaluate_ablation,
)
from services.evaluation.significance import compare_paired, paired_t_test


def test_ablation_evaluates_all_variants() -> None:
    rankings = {
        "sbert_only": {
            "u1": ["j1", "j2", "j3"],
            "u2": ["j2", "j4"],
        },
        "ncf_only": {
            "u1": ["j2", "j1", "j3"],
            "u2": ["j4", "j2"],
        },
        "full_scpa": {
            "u1": ["j1", "j2", "j3"],
            "u2": ["j2", "j4"],
        },
    }
    relevant = {"u1": {"j1"}, "u2": {"j4"}}
    report = evaluate_ablation(rankings, relevant, k=2)
    assert set(report.keys()) == {"sbert_only", "ncf_only", "full_scpa"}
    for metrics in report.values():
        assert "precision_at_k" in metrics
        assert "recall_at_k" in metrics
        assert "ndcg_at_k" in metrics
        assert "hit_rate_at_k" in metrics


def test_ablation_summary_table() -> None:
    report = {
        "sbert_only": {"precision_at_k": 0.5, "recall_at_k": 0.3},
    }
    rows = ablation_summary_table(report)
    assert rows == [{"variant": "sbert_only", "precision_at_k": 0.5, "recall_at_k": 0.3}]


def test_paired_t_test_on_known_example() -> None:
    deltas = [0.1, 0.15, 0.12, 0.18, 0.11, 0.14, 0.13, 0.16, 0.12, 0.15]
    t, p = paired_t_test(deltas)
    assert t > 0
    assert 0.0 < p < 1.0


def test_compare_paired_significant_when_treatment_better() -> None:
    baseline = {f"q{i}": 0.2 for i in range(30)}
    treatment = {f"q{i}": 0.35 for i in range(30)}
    result = compare_paired(baseline, treatment, alpha=0.05)
    assert result["test_used"] == "paired_t_test"
    assert result["n_queries"] == 30
    assert result["effect_size"] > 0
    assert result["significant"] is True
    assert result["p_value"] < 0.05


def test_compare_paired_not_significant_when_equal() -> None:
    baseline = {f"q{i}": 0.5 for i in range(30)}
    treatment = {f"q{i}": 0.5 for i in range(30)}
    result = compare_paired(baseline, treatment, alpha=0.05)
    assert result["significant"] is False
    assert result["p_value"] == pytest.approx(1.0, abs=1e-6)


def test_compare_paired_uses_wilcoxon_for_small_n() -> None:
    baseline = {"q1": 0.2, "q2": 0.3, "q3": 0.1}
    treatment = {"q1": 0.4, "q2": 0.5, "q3": 0.3}
    result = compare_paired(baseline, treatment, alpha=0.05)
    assert result["test_used"] == "wilcoxon_signed_rank"
    assert result["n_queries"] == 3


def test_ablation_variants_list_is_complete() -> None:
    assert set(ABLATION_VARIANTS) == {
        "sbert_only",
        "ncf_only",
        "dqn_only",
        "sbert_ncf",
        "sbert_dqn",
        "ncf_dqn",
        "full_scpa",
    }
