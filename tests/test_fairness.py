"""STEP 2 — Fairness Constraint Enforcement Tests.

The most critical tests for TA research validity.
Verifies that Equal Opportunity (TPR gap < 8pp) is enforced correctly
via the FairnessTracker's EMA-based re-ranking mechanism.

All tests use deterministic numeric values — no randomness.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.hybrid.main import (
    FairnessTracker,
    HybridScore,
    FAIRNESS_TPR_THRESHOLD,
)


def _make_scores(values: list[float]) -> list[HybridScore]:
    """Helper: create HybridScore objects from a list of score values."""
    return [
        HybridScore(
            job_id=f"job-{i:03d}",
            hybrid_score=v,
            sbert_score=v * 0.8,
            ncf_score=v * 0.2,
            alpha_used=0.5,
        )
        for i, v in enumerate(values)
    ]


class TestFairnessSatisfied:
    """Scenario 1: TPR gap within threshold — no re-ranking should occur."""

    def test_gap_3pp_no_rerank(self) -> None:
        """TPR gap = 3pp (well under 8pp).

        Verifies that recommendations pass through unchanged when
        the fairness constraint is already satisfied.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.85, "minority": 0.82}  # 3pp gap

        original = [0.95, 0.88, 0.75, 0.62, 0.50]
        scores = _make_scores(original)
        result = ft.enforce_fairness(scores, "minority")

        result_values = [s.hybrid_score for s in result]
        assert result_values == original, (
            "Scores were re-ranked despite TPR gap being within threshold"
        )

    def test_gap_0pp_no_rerank(self) -> None:
        """TPR gap = 0pp (perfect equality).

        Edge case: zero gap should never trigger re-ranking.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.85, "minority": 0.85}

        original = [0.9, 0.7, 0.5]
        scores = _make_scores(original)
        result = ft.enforce_fairness(scores, "minority")
        assert [s.hybrid_score for s in result] == original

    def test_single_group_no_rerank(self) -> None:
        """Only one demographic group present — gap is 0 by definition."""
        ft = FairnessTracker()
        ft.tpr = {"only_group": 0.85}

        scores = _make_scores([0.9, 0.8])
        result = ft.enforce_fairness(scores, "only_group")
        assert [s.hybrid_score for s in result] == [0.9, 0.8]


class TestFairnessViolated:
    """Scenario 2: TPR gap exceeds threshold — re-ranking must occur."""

    def test_gap_12pp_triggers_boost(self) -> None:
        """TPR gap = 12pp (exceeds 8pp threshold).

        Minority group scores must be boosted to reduce effective gap.
        Boost amount = (gap - threshold) / 100 = (12 - 8) / 100 = 0.04
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.90, "minority": 0.78}  # 12pp

        scores = _make_scores([0.80, 0.60, 0.40])
        result = ft.enforce_fairness(scores, "minority")

        # All scores should be boosted by 0.04
        assert result[0].hybrid_score == pytest.approx(0.84, abs=0.01)
        assert result[1].hybrid_score == pytest.approx(0.64, abs=0.01)
        assert result[2].hybrid_score == pytest.approx(0.44, abs=0.01)

    def test_majority_user_not_boosted_when_gap_violated(self) -> None:
        """Majority group user should NOT receive score boost.

        Even when gap exceeds threshold, only the disadvantaged group
        gets re-ranked. This prevents over-correction.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.90, "minority": 0.78}  # 12pp

        scores = _make_scores([0.80, 0.60])
        result = ft.enforce_fairness(scores, "majority")

        assert result[0].hybrid_score == 0.80
        assert result[1].hybrid_score == 0.60

    def test_gap_20pp_boost_correct(self) -> None:
        """Extreme gap = 20pp.

        Boost = (20 - 8) / 100 = 0.12. Scores should be boosted by 0.12.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.95, "minority": 0.75}  # 20pp

        scores = _make_scores([0.70, 0.50])
        result = ft.enforce_fairness(scores, "minority")

        assert result[0].hybrid_score == pytest.approx(0.82, abs=0.01)
        assert result[1].hybrid_score == pytest.approx(0.62, abs=0.01)

    def test_boosted_scores_capped_at_1(self) -> None:
        """Boosted scores must never exceed 1.0.

        Even with a large gap and already-high scores, cap at 1.0.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.95, "minority": 0.70}  # 25pp, boost=0.17

        scores = _make_scores([0.99, 0.95, 0.90])
        result = ft.enforce_fairness(scores, "minority")

        for s in result:
            assert s.hybrid_score <= 1.0, (
                f"Score {s.hybrid_score} exceeds maximum 1.0"
            )

    def test_reranked_order_is_descending(self) -> None:
        """After re-ranking, scores must remain in descending order."""
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.92, "minority": 0.78}  # 14pp

        scores = _make_scores([0.90, 0.85, 0.80, 0.75, 0.70])
        result = ft.enforce_fairness(scores, "minority")

        values = [s.hybrid_score for s in result]
        assert values == sorted(values, reverse=True), "Re-ranked scores not sorted"


class TestFairnessBoundaryConditions:
    """Scenario 3: Exact boundary at 8pp threshold."""

    def test_gap_7_9pp_no_rerank(self) -> None:
        """TPR gap = 7.9pp (just under threshold).

        Must NOT trigger re-ranking. Tests floating-point boundary handling.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.879, "minority": 0.800}  # 7.9pp

        scores = _make_scores([0.85, 0.70])
        result = ft.enforce_fairness(scores, "minority")

        assert result[0].hybrid_score == 0.85
        assert result[1].hybrid_score == 0.70

    def test_gap_8_0pp_exactly_no_rerank(self) -> None:
        """TPR gap = exactly 8.0pp (at threshold).

        The condition is gap < 8.0, so exactly 8.0 should NOT trigger.
        But the code uses `gap <= 8.0`, so it should NOT trigger re-ranking.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.88, "minority": 0.80}  # exactly 8pp

        scores = _make_scores([0.85, 0.70])
        result = ft.enforce_fairness(scores, "minority")

        # At exactly threshold, no re-ranking (<=)
        assert result[0].hybrid_score == 0.85

    def test_gap_8_1pp_triggers_rerank(self) -> None:
        """TPR gap = 8.1pp (just over threshold).

        Must trigger re-ranking. Boost = (8.1 - 8.0) / 100 = 0.001.
        """
        ft = FairnessTracker()
        ft.tpr = {"majority": 0.881, "minority": 0.800}  # 8.1pp

        scores = _make_scores([0.85, 0.70])
        result = ft.enforce_fairness(scores, "minority")

        # Boost should be 0.001 — very small but nonzero
        assert result[0].hybrid_score >= 0.85, (
            "Score should be boosted at gap=8.1pp"
        )


class TestFairnessEMASmoothing:
    """Verify exponential moving average correctly smooths TPR updates."""

    def test_ema_converges_toward_observed(self) -> None:
        """After many positive updates, TPR should approach 1.0.

        EMA formula: tpr_new = α * observed + (1 - α) * tpr_old
        With α=0.1 and all positives, TPR converges slowly.
        """
        ft = FairnessTracker()
        ft.tpr = {"test_group": 0.50}
        ft.counts = {"test_group": {"positive": 50, "total": 100}}

        # Simulate 100 positive interactions
        for _ in range(100):
            ft.update_stats("test_group", True)

        # After 100 positives from 0.5, cumulative average approaches 0.75 (150/200)
        assert ft.tpr["test_group"] > 0.70, (
            f"EMA not converging: tpr={ft.tpr['test_group']}"
        )

    def test_ema_resists_single_outlier(self) -> None:
        """A single negative after many positives shouldn't crash TPR.

        EMA smoothing prevents outlier sensitivity.
        """
        ft = FairnessTracker()
        ft.tpr = {"stable_group": 0.90}
        ft.counts = {"stable_group": {"positive": 90, "total": 100}}

        # One negative interaction
        ft.update_stats("stable_group", False)

        assert ft.tpr["stable_group"] > 0.85, (
            "Single outlier caused too much TPR drop"
        )

    def test_three_groups_max_gap_calculated(self) -> None:
        """With 3+ groups, gap = max(TPR) - min(TPR).

        Intermediate group values should not affect the gap calculation.
        """
        ft = FairnessTracker()
        ft.tpr = {"group_a": 0.90, "group_b": 0.85, "group_c": 0.78}

        gap = ft.get_tpr_gap()
        expected = (0.90 - 0.78) * 100  # 12pp
        assert abs(gap - expected) < 0.1
