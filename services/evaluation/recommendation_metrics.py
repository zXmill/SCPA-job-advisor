"""Reusable recommendation metrics for SCPA evaluation notebooks and tests."""

from __future__ import annotations

import math
from itertools import combinations
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


RelevantInput = set[str] | Mapping[str, float]


def _as_gain_map(relevant: RelevantInput) -> dict[str, float]:
    if isinstance(relevant, Mapping):
        return {str(item_id): float(gain) for item_id, gain in relevant.items() if float(gain) > 0.0}
    return {str(item_id): 1.0 for item_id in relevant}


def _top_k(ranked_ids: Sequence[str], k: int) -> list[str]:
    if k <= 0:
        return []
    top: list[str] = []
    seen: set[str] = set()
    for item_id in ranked_ids:
        item_id = str(item_id)
        if item_id in seen:
            continue
        seen.add(item_id)
        top.append(item_id)
        if len(top) >= k:
            break
    return top


def precision_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return binary Precision@K using the available top-K list length."""
    gains = _as_gain_map(relevant)
    top = _top_k(ranked_ids, k)
    if not gains or not top:
        return 0.0
    hits = sum(1 for item_id in top if item_id in gains)
    return hits / len(top)


def recall_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return Recall@K for binary relevance."""
    gains = _as_gain_map(relevant)
    if not gains:
        return 0.0
    top = set(_top_k(ranked_ids, k))
    hits = sum(1 for item_id in gains if item_id in top)
    return hits / len(gains)


def hit_rate_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return 1.0 when at least one relevant item is present in top K."""
    gains = _as_gain_map(relevant)
    if not gains:
        return 0.0
    top = set(_top_k(ranked_ids, k))
    return 1.0 if any(item_id in top for item_id in gains) else 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return NDCG@K with binary or graded relevance gains."""
    gains = _as_gain_map(relevant)
    if not gains:
        return 0.0
    dcg = 0.0
    for rank, item_id in enumerate(_top_k(ranked_ids, k), start=1):
        gain = gains.get(item_id, 0.0)
        if gain:
            dcg += gain / math.log2(rank + 1)
    ideal_gains = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal_gains, start=1))
    return dcg / idcg if idcg else 0.0


def average_precision_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return AP@K for one user using binary relevance."""
    gains = _as_gain_map(relevant)
    if not gains:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for rank, item_id in enumerate(_top_k(ranked_ids, k), start=1):
        if item_id in gains:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / min(len(gains), max(k, 1))


def reciprocal_rank_at_k(ranked_ids: Sequence[str], relevant: RelevantInput, k: int) -> float:
    """Return reciprocal rank of the first relevant item in top K."""
    gains = _as_gain_map(relevant)
    if not gains:
        return 0.0
    for rank, item_id in enumerate(_top_k(ranked_ids, k), start=1):
        if item_id in gains:
            return 1.0 / rank
    return 0.0


def mean_metric(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def map_at_k(rankings: Mapping[str, Sequence[str]], relevant_by_user: Mapping[str, RelevantInput], k: int) -> float:
    return mean_metric(
        average_precision_at_k(rankings.get(user_id, []), relevant, k)
        for user_id, relevant in relevant_by_user.items()
    )


def mrr_at_k(rankings: Mapping[str, Sequence[str]], relevant_by_user: Mapping[str, RelevantInput], k: int) -> float:
    return mean_metric(
        reciprocal_rank_at_k(rankings.get(user_id, []), relevant, k)
        for user_id, relevant in relevant_by_user.items()
    )


def ctr_proxy(
    interactions: Sequence[Mapping[str, Any]],
    *,
    positive_events: set[str] | None = None,
    denominator_events: set[str] | None = None,
) -> float:
    """Estimate CTR from logged behavior rows when full impression logs are unavailable."""
    positive_events = positive_events or {"click", "save", "apply"}
    denominator_events = denominator_events or {"impression", "click", "save", "apply", "view", "skip"}
    denominator = [
        row for row in interactions
        if str(row.get("event") or "").lower() in denominator_events
    ]
    if not denominator:
        return 0.0
    positives = [
        row for row in denominator
        if str(row.get("event") or "").lower() in positive_events
    ]
    return len(positives) / len(denominator)


def catalog_coverage(rankings: Mapping[str, Sequence[str]], catalog_ids: Iterable[str], k: int) -> float:
    catalog = {str(item_id) for item_id in catalog_ids}
    if not catalog:
        return 0.0
    recommended = {
        item_id
        for ranked_ids in rankings.values()
        for item_id in _top_k(ranked_ids, k)
    }
    return len(recommended & catalog) / len(catalog)


def intra_list_diversity(
    rankings: Mapping[str, Sequence[str]],
    item_features: Mapping[str, Iterable[str]],
    k: int,
) -> float:
    """Return mean pairwise Jaccard distance for recommended item feature sets."""
    per_user: list[float] = []
    feature_sets = {
        str(item_id): {str(feature).lower() for feature in features}
        for item_id, features in item_features.items()
    }
    for ranked_ids in rankings.values():
        pairs = list(combinations(_top_k(ranked_ids, k), 2))
        if not pairs:
            continue
        distances: list[float] = []
        for left, right in pairs:
            left_features = feature_sets.get(left, set())
            right_features = feature_sets.get(right, set())
            union = left_features | right_features
            if not union:
                distances.append(0.0)
            else:
                distances.append(1.0 - (len(left_features & right_features) / len(union)))
        per_user.append(mean_metric(distances))
    return mean_metric(per_user)


def fairness_gap_tpr_at_k(
    rankings: Mapping[str, Sequence[str]],
    relevant_by_user: Mapping[str, RelevantInput],
    group_by_user: Mapping[str, str],
    k: int,
) -> dict[str, Any]:
    """Return group TPRs and max-min fairness gap in percentage points."""
    grouped: dict[str, list[float]] = {}
    for user_id, relevant in relevant_by_user.items():
        group = str(group_by_user.get(user_id, "unknown"))
        grouped.setdefault(group, []).append(hit_rate_at_k(rankings.get(user_id, []), relevant, k))
    group_tpr = {group: mean_metric(values) for group, values in grouped.items()}
    gap = (max(group_tpr.values()) - min(group_tpr.values())) * 100.0 if len(group_tpr) > 1 else 0.0
    return {"group_tpr": group_tpr, "fairness_gap_pp": gap}


def p95_latency_ms(latencies_ms: Sequence[float]) -> float:
    if not latencies_ms:
        return 0.0
    ordered = sorted(float(value) for value in latencies_ms)
    index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def ranking_report(
    rankings: Mapping[str, Sequence[str]],
    relevant_by_user: Mapping[str, RelevantInput],
    *,
    k_values: Sequence[int] = (5, 10),
) -> dict[str, float]:
    """Compute core ranking metrics for all requested K values."""
    report: dict[str, float] = {}
    for k in k_values:
        report[f"precision_at_{k}"] = mean_metric(
            precision_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        report[f"recall_at_{k}"] = mean_metric(
            recall_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        report[f"ndcg_at_{k}"] = mean_metric(
            ndcg_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        report[f"hit_rate_at_{k}"] = mean_metric(
            hit_rate_at_k(rankings.get(user_id, []), relevant, k)
            for user_id, relevant in relevant_by_user.items()
        )
        report[f"map_at_{k}"] = map_at_k(rankings, relevant_by_user, k)
        report[f"mrr_at_{k}"] = mrr_at_k(rankings, relevant_by_user, k)
    return report
