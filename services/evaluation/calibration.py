"""Evaluation smoke checks for the recommendation calibration layer."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Mapping

from services.evaluation.recommendation_metrics import mean_metric, ndcg_at_k
from services.pipeline.calibration import (
    CALIBRATOR_BASELINE,
    calibrated_score,
    get_default_calibrator,
    synthetic_calibration_examples,
)


def _ranked_ids(items: list[dict[str, Any]], score_key: str) -> list[str]:
    return [
        str(item["id"])
        for item in sorted(items, key=lambda item: float(item[score_key]), reverse=True)
    ]


def _smoke_items() -> dict[str, list[dict[str, Any]]]:
    examples = synthetic_calibration_examples()
    return {
        "u-smoke-1": [
            {
                "id": "static-favored",
                "static_score": examples[0][0]["static_score"],
                "calibrated_score": calibrated_score(examples[0][0]),
            },
            {
                "id": "calibrated-fit",
                "static_score": examples[1][0]["static_score"],
                "calibrated_score": calibrated_score(examples[1][0]),
            },
            {
                "id": "weak-fit",
                "static_score": examples[5][0]["static_score"],
                "calibrated_score": calibrated_score(examples[5][0]),
            },
        ],
        "u-smoke-2": [
            {
                "id": "strong-fit",
                "static_score": examples[2][0]["static_score"],
                "calibrated_score": calibrated_score(examples[2][0]),
            },
            {
                "id": "semantic-mismatch",
                "static_score": examples[3][0]["static_score"],
                "calibrated_score": calibrated_score(examples[3][0]),
            },
            {
                "id": "location-fit",
                "static_score": examples[4][0]["static_score"],
                "calibrated_score": calibrated_score(examples[4][0]),
            },
        ],
    }


def build_calibration_smoke_report() -> dict[str, Any]:
    """Compare learned calibration against the static baseline on a smoke fixture.

    This is a deterministic engineering smoke check, not a production-quality
    offline metric.
    """
    items_by_user = _smoke_items()
    relevant_by_user: Mapping[str, Mapping[str, float]] = {
        "u-smoke-1": {"calibrated-fit": 3.0, "static-favored": 0.1},
        "u-smoke-2": {"strong-fit": 3.0, "location-fit": 2.0},
    }
    static_rankings = {
        user_id: _ranked_ids(items, "static_score")
        for user_id, items in items_by_user.items()
    }
    calibrated_rankings = {
        user_id: _ranked_ids(items, "calibrated_score")
        for user_id, items in items_by_user.items()
    }
    static_ndcg = mean_metric(
        ndcg_at_k(static_rankings[user_id], relevant, 3)
        for user_id, relevant in relevant_by_user.items()
    )
    calibrated_ndcg = mean_metric(
        ndcg_at_k(calibrated_rankings[user_id], relevant, 3)
        for user_id, relevant in relevant_by_user.items()
    )
    model = get_default_calibrator()
    return {
        "dataset": "synthetic_calibration_smoke_v1",
        "baseline": CALIBRATOR_BASELINE,
        "evaluation_scope": "deterministic smoke fixture; not production performance evidence",
        "calibrator": model.summary(),
        "metrics": {
            "static_baseline_ndcg_at_3": round(static_ndcg, 6),
            "calibrated_ndcg_at_3": round(calibrated_ndcg, 6),
            "ndcg_lift": round(calibrated_ndcg - static_ndcg, 6),
        },
        "rankings": {
            "static_baseline": static_rankings,
            "learned_calibrator": calibrated_rankings,
        },
    }


def write_calibration_smoke_report(path: str | Path = "reports/ml/calibration_layer_smoke.json") -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_calibration_smoke_report(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path
