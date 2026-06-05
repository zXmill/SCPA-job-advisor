"""Statistical significance tests for paired recommender metric comparisons.

Paired t-test for approximately-normal deltas, Wilcoxon signed-rank otherwise.
"""

from __future__ import annotations

import math
from statistics import mean, stdev
from typing import Any


def _student_t_pdf(x: float, df: int) -> float:
    coefficient = math.exp(
        math.lgamma((df + 1.0) / 2.0)
        - math.lgamma(df / 2.0)
        - 0.5 * math.log(df * math.pi)
    )
    return coefficient * (1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0)


def _adaptive_simpson(
    func,
    left: float,
    right: float,
    eps: float,
    whole: float,
    depth: int,
) -> float:
    mid = (left + right) / 2.0
    left_mid = (left + mid) / 2.0
    right_mid = (mid + right) / 2.0
    left_area = (mid - left) * (func(left) + 4.0 * func(left_mid) + func(mid)) / 6.0
    right_area = (right - mid) * (func(mid) + 4.0 * func(right_mid) + func(right)) / 6.0
    delta = left_area + right_area - whole
    if depth <= 0 or abs(delta) <= 15.0 * eps:
        return left_area + right_area + delta / 15.0
    return _adaptive_simpson(func, left, mid, eps / 2.0, left_area, depth - 1) + _adaptive_simpson(
        func, mid, right, eps / 2.0, right_area, depth - 1
    )


def _student_t_two_sided_p(t_stat: float, df: int) -> float:
    """Numerically integrate Student's t density for a two-sided p-value."""
    if df <= 0:
        return 1.0
    t_abs = abs(t_stat)
    if t_abs == 0:
        return 1.0
    if t_abs > 50:
        return 0.0
    pdf = lambda x: _student_t_pdf(x, df)
    whole = t_abs * (pdf(0.0) + 4.0 * pdf(t_abs / 2.0) + pdf(t_abs)) / 6.0
    cdf_offset = _adaptive_simpson(pdf, 0.0, t_abs, 1e-8, whole, 20)
    return max(0.0, min(1.0, 1.0 - 2.0 * cdf_offset))


def _wilcoxon_signed_rank(deltas: list[float]) -> tuple[float, float]:
    """Compute Wilcoxon signed-rank statistic and approximate two-sided p-value."""
    n = len(deltas)
    if n < 2:
        return 0.0, 1.0

    abs_deltas = [abs(d) for d in deltas]
    ranked = sorted(enumerate(abs_deltas), key=lambda x: x[1])
    ranks = [0.0] * n
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][1] == ranked[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for idx in range(i, j + 1):
            original_index = ranked[idx][0]
            ranks[original_index] = avg_rank
        i = j + 1

    w_plus = sum(ranks[i] for i in range(n) if deltas[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if deltas[i] < 0)
    w = min(w_plus, w_minus)

    mu = n * (n + 1) / 4.0
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if sigma == 0:
        return w, 1.0

    z = (w - mu) / sigma
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2))))
    return w, p


def paired_t_test(deltas: list[float]) -> tuple[float, float]:
    """Return (t_statistic, p_value) for paired t-test.

    Uses Student's t with n-1 degrees of freedom. For n >= 30, approximates
    with normal distribution.
    """
    n = len(deltas)
    if n < 2:
        return 0.0, 1.0
    m = mean(deltas)
    s = stdev(deltas)
    if s == 0:
        if m == 0:
            return 0.0, 1.0
        return float("inf") if m > 0 else float("-inf"), 0.0
    t = m / (s / math.sqrt(n))

    return t, _student_t_two_sided_p(t, n - 1)


def compare_paired(
    baseline_scores: dict[str, float],
    treatment_scores: dict[str, float],
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compare two models on paired metric values per user/query.

    Args:
        baseline_scores: {query_id: metric_value}
        treatment_scores: {query_id: metric_value}
        alpha: significance threshold

    Returns:
        Dict with test_used, statistic, p_value, significant, effect_size,
        confidence_interval, and n_queries.
    """
    common_keys = sorted(set(baseline_scores) & set(treatment_scores))
    if not common_keys:
        return {
            "test_used": "none",
            "statistic": 0.0,
            "p_value": 1.0,
            "significant": False,
            "effect_size": 0.0,
            "confidence_interval": [0.0, 0.0],
            "n_queries": 0,
        }

    deltas = [treatment_scores[k] - baseline_scores[k] for k in common_keys]
    n = len(deltas)

    m = mean(deltas)
    if n >= 2:
        s = stdev(deltas)
        se = s / math.sqrt(n)
        ci_lower = m - 1.96 * se
        ci_upper = m + 1.96 * se
    else:
        ci_lower = ci_upper = m

    effect_size = m / (stdev(deltas) if n >= 2 and stdev(deltas) > 0 else 1.0)

    if n >= 30:
        t, p = paired_t_test(deltas)
        return {
            "test_used": "paired_t_test",
            "statistic": t,
            "p_value": p,
            "significant": p < alpha,
            "effect_size": effect_size,
            "confidence_interval": [ci_lower, ci_upper],
            "n_queries": n,
        }

    w, p = _wilcoxon_signed_rank(deltas)
    return {
        "test_used": "wilcoxon_signed_rank",
        "statistic": w,
        "p_value": p,
        "significant": p < alpha,
        "effect_size": effect_size,
        "confidence_interval": [ci_lower, ci_upper],
        "n_queries": n,
    }
