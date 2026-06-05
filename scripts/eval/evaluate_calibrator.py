"""Evaluate recommendation calibrator performance.

P5-ML-005: Compare calibrated scores against static baseline on labeled
calibration examples. Report NDCG lift and per-feature importance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.pipeline.calibration import (
    get_default_calibrator,
    calibrated_score,
    synthetic_calibration_examples,
)
from services.evaluation.recommendation_metrics import ndcg_at_k, mean_metric


def evaluate_calibrator(
    output_dir: Path,
    k_values: tuple[int, ...] = (3, 5),
) -> dict[str, Any]:
    examples = synthetic_calibration_examples()
    calibrator = get_default_calibrator()

    # Group examples into artificial "users" (2 items per user) for ranking evaluation
    items_per_user = 2
    items_by_user: dict[str, list[dict[str, float]]] = {}
    relevant_by_user: dict[str, dict[str, float]] = {}

    for idx, (features, label) in enumerate(examples):
        user_id = f"u-{idx // items_per_user}"
        item_id = f"item-{idx}"
        items_by_user.setdefault(user_id, []).append({
            "id": item_id,
            "static_score": float(features["static_score"]),
            "calibrated_score": float(calibrated_score(features, calibrator)),
            "label": float(label),
        })

    # For each user, relevant items are those with label == 1.0
    for user_id, items in items_by_user.items():
        relevant_by_user[user_id] = {
            item["id"]: item["label"] for item in items if item["label"] > 0.5
        }

    static_rankings = {
        uid: [item["id"] for item in sorted(items, key=lambda x: x["static_score"], reverse=True)]
        for uid, items in items_by_user.items()
    }
    calibrated_rankings = {
        uid: [item["id"] for item in sorted(items, key=lambda x: x["calibrated_score"], reverse=True)]
        for uid, items in items_by_user.items()
    }

    report: dict[str, Any] = {
        "dataset": "synthetic_calibration_smoke_v1",
        "calibrator": calibrator.summary(),
        "n_queries": len(items_by_user),
    }

    for k in k_values:
        static_ndcg = mean_metric(
            ndcg_at_k(static_rankings[uid], relevant_by_user[uid], k)
            for uid in items_by_user
        )
        calibrated_ndcg = mean_metric(
            ndcg_at_k(calibrated_rankings[uid], relevant_by_user[uid], k)
            for uid in items_by_user
        )
        report[f"static_ndcg_at_{k}"] = round(static_ndcg, 6)
        report[f"calibrated_ndcg_at_{k}"] = round(calibrated_ndcg, 6)
        report[f"ndcg_lift_at_{k}"] = round(calibrated_ndcg - static_ndcg, 6)

    # Weight analysis
    total_weight = sum(abs(w) for w in calibrator.weights.values())
    feature_importance = {
        name: round(abs(calibrator.weights.get(name, 0.0)) / total_weight, 4) if total_weight > 0 else 0.0
        for name in calibrator.feature_names
    }
    report["feature_importance"] = feature_importance

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "calibrator_evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/calibrator"))
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5])
    args = parser.parse_args()
    report = evaluate_calibrator(args.output_dir, k_values=tuple(args.k))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
