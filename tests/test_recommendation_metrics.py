"""Deterministic checks for recommender ranking metrics."""

from __future__ import annotations

import pytest

from services.evaluation.recommendation_metrics import (
    average_precision_at_k,
    catalog_coverage,
    ctr_proxy,
    fairness_gap_tpr_at_k,
    hit_rate_at_k,
    intra_list_diversity,
    map_at_k,
    mrr_at_k,
    ndcg_at_k,
    p95_latency_ms,
    precision_at_k,
    ranking_report,
    recall_at_k,
    reciprocal_rank_at_k,
)


def test_ranking_metrics_on_known_example() -> None:
    ranked = ["job-a", "job-b", "job-c", "job-d"]
    relevant = {"job-a", "job-c"}

    assert precision_at_k(ranked, relevant, k=2) == pytest.approx(0.5)
    assert recall_at_k(ranked, relevant, k=2) == pytest.approx(0.5)
    assert hit_rate_at_k(ranked, relevant, k=2) == pytest.approx(1.0)
    assert ndcg_at_k(ranked, relevant, k=2) == pytest.approx(0.613147, abs=1e-6)
    assert average_precision_at_k(ranked, relevant, k=3) == pytest.approx(5 / 6)
    assert reciprocal_rank_at_k(ranked, relevant, k=3) == pytest.approx(1.0)


def test_empty_relevance_returns_zero() -> None:
    ranked = ["job-a", "job-b"]

    assert precision_at_k(ranked, set(), k=2) == pytest.approx(0.0)
    assert recall_at_k(ranked, set(), k=2) == pytest.approx(0.0)
    assert hit_rate_at_k(ranked, set(), k=2) == pytest.approx(0.0)
    assert ndcg_at_k(ranked, set(), k=2) == pytest.approx(0.0)


def test_empty_recommendations_return_zero_with_positive_relevance() -> None:
    relevant = {"job-a"}

    assert precision_at_k([], relevant, k=5) == pytest.approx(0.0)
    assert recall_at_k([], relevant, k=5) == pytest.approx(0.0)
    assert hit_rate_at_k([], relevant, k=5) == pytest.approx(0.0)
    assert ndcg_at_k([], relevant, k=5) == pytest.approx(0.0)
    assert average_precision_at_k([], relevant, k=5) == pytest.approx(0.0)
    assert reciprocal_rank_at_k([], relevant, k=5) == pytest.approx(0.0)


def test_k_larger_than_available_recommendations_uses_available_length() -> None:
    ranked = ["job-a"]
    relevant = {"job-a", "job-b"}

    assert precision_at_k(ranked, relevant, k=10) == pytest.approx(1.0)
    assert recall_at_k(ranked, relevant, k=10) == pytest.approx(0.5)
    assert hit_rate_at_k(ranked, relevant, k=10) == pytest.approx(1.0)


def test_duplicate_recommendations_do_not_inflate_metrics() -> None:
    ranked = ["job-a", "job-a", "job-b"]
    relevant = {"job-a"}

    assert precision_at_k(ranked, relevant, k=3) == pytest.approx(0.5)
    assert recall_at_k(ranked, relevant, k=3) == pytest.approx(1.0)
    assert ndcg_at_k(ranked, relevant, k=3) == pytest.approx(1.0)
    assert average_precision_at_k(ranked, relevant, k=3) == pytest.approx(1.0)


def test_mean_ranking_metrics_on_known_users() -> None:
    rankings = {"user-1": ["job-a", "job-b", "job-c"], "user-2": ["job-x", "job-y"]}
    relevant_by_user = {"user-1": {"job-a", "job-c"}, "user-2": {"job-z"}}

    assert map_at_k(rankings, relevant_by_user, k=3) == pytest.approx(5 / 12)
    assert mrr_at_k(rankings, relevant_by_user, k=3) == pytest.approx(0.5)

    report = ranking_report(rankings, relevant_by_user, k_values=(3,))
    assert report["precision_at_3"] == pytest.approx((2 / 3) / 2)
    assert report["recall_at_3"] == pytest.approx(0.5)
    assert report["hit_rate_at_3"] == pytest.approx(0.5)
    assert report["map_at_3"] == pytest.approx(5 / 12)
    assert report["mrr_at_3"] == pytest.approx(0.5)


def test_ctr_proxy_on_known_events() -> None:
    interactions = [
        {"event": "apply"},
        {"event": "click"},
        {"event": "save"},
        {"event": "skip"},
        {"event": "impression"},
        {"event": "view"},
    ]

    assert ctr_proxy(interactions) == pytest.approx(0.5)


def test_coverage_diversity_fairness_and_latency_known_values() -> None:
    rankings = {"user-1": ["job-a", "job-b", "job-c"], "user-2": ["job-b", "job-c"]}

    assert catalog_coverage(rankings, {"job-a", "job-b", "job-c", "job-d"}, k=2) == pytest.approx(0.75)
    assert intra_list_diversity(
        {"user-1": ["job-a", "job-b", "job-c"]},
        {
            "job-a": {"python", "sql"},
            "job-b": {"python"},
            "job-c": {"figma"},
        },
        k=3,
    ) == pytest.approx(5 / 6)

    fairness = fairness_gap_tpr_at_k(
        {"user-1": ["job-a"], "user-2": ["job-x"]},
        {"user-1": {"job-a"}, "user-2": {"job-z"}},
        {"user-1": "early-career", "user-2": "career-switcher"},
        k=1,
    )
    assert fairness["group_tpr"]["early-career"] == pytest.approx(1.0)
    assert fairness["group_tpr"]["career-switcher"] == pytest.approx(0.0)
    assert fairness["fairness_gap_pp"] == pytest.approx(100.0)
    assert p95_latency_ms([1, 2, 3, 100]) == pytest.approx(100.0)
