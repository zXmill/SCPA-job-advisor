"""Ablation study framework for SCPA hybrid recommender.

Supports comparing:
- SBERT only
- NCF only
- DQN only
- SBERT + NCF
- SBERT + DQN
- NCF + DQN
- Full SCPA (SBERT + NCF + DQN)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from services.evaluation.recommendation_metrics import (
    hit_rate_at_k,
    mean_metric,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

RelevantInput = set[str] | Mapping[str, float]

ABLATION_VARIANTS = [
    "sbert_only",
    "ncf_only",
    "dqn_only",
    "sbert_ncf",
    "sbert_dqn",
    "ncf_dqn",
    "full_scpa",
]


def evaluate_ablation(
    rankings_by_variant: Mapping[str, Mapping[str, Sequence[str]]],
    relevant_by_user: Mapping[str, RelevantInput],
    *,
    k: int = 10,
) -> dict[str, dict[str, float]]:
    """Compute metrics for every ablation variant.

    Args:
        rankings_by_variant: {variant_name: {user_id: [job_id, ...]}}
        relevant_by_user: {user_id: relevant_set}
        k: cutoff for metrics

    Returns:
        {variant_name: {metric_name: float}}
    """
    report: dict[str, dict[str, float]] = {}
    for variant, rankings in rankings_by_variant.items():
        metrics: dict[str, float] = {}
        metrics["precision_at_k"] = mean_metric(
            precision_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        metrics["recall_at_k"] = mean_metric(
            recall_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        metrics["ndcg_at_k"] = mean_metric(
            ndcg_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        metrics["hit_rate_at_k"] = mean_metric(
            hit_rate_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        report[variant] = metrics
    return report


def ablation_summary_table(report: Mapping[str, Mapping[str, float]]) -> list[dict[str, Any]]:
    """Flatten ablation report into a table-friendly list of rows."""
    rows: list[dict[str, Any]] = []
    for variant, metrics in report.items():
        row = {"variant": variant}
        row.update(metrics)
        rows.append(row)
    return rows
