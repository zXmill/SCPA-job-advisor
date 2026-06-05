"""Contracts for the learned recommendation calibration layer."""

from __future__ import annotations

import pytest

from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage


REQUIRED_CALIBRATION_FEATURES = {
    "sbert_score",
    "ncf_score",
    "dqn_signal",
    "alignment_gap",
    "recency_score",
    "salary_score",
    "location_score",
}


@pytest.mark.anyio
async def test_aggregate_emits_learned_calibration_and_static_baseline() -> None:
    user = {
        "id": "u-calibration",
        "interaction_count": 35,
        "profile_text": "Python backend developer",
        "skills": ["Python", "FastAPI"],
        "location": "Jakarta",
        "expected_salary_min": 12_000_000,
    }
    jobs = [
        {
            "id": "static-favored",
            "title": "Backend Developer",
            "location": "United States",
            "sbert_score": 0.86,
            "ncf_score": 0.18,
            "dqn_score": 0.12,
            "posted_at": "2025-01-01T00:00:00+00:00",
            "min_salary": 3_000_000,
            "max_salary": 4_000_000,
        },
        {
            "id": "calibrated-fit",
            "title": "FastAPI Engineer",
            "location": "Jakarta, Indonesia",
            "sbert_score": 0.62,
            "ncf_score": 0.62,
            "dqn_score": 0.72,
            "posted_at": "2026-05-20T00:00:00+00:00",
            "min_salary": 15_000_000,
            "max_salary": 20_000_000,
        },
    ]

    result = await run_aggregate_stage(user, jobs)

    calibrator = result.summary["calibrator"]
    assert calibrator["mode"] == "learned_logistic"
    assert calibrator["baseline"] == "static_weighted_hybrid"
    assert REQUIRED_CALIBRATION_FEATURES <= set(calibrator["feature_names"])

    first = result.ranked[0]
    assert first["id"] == "calibrated-fit"
    assert first["final_score"] == pytest.approx(0.64)
    assert first["calibrated_score"] != first["final_score"]
    assert first["calibration_note"] == "calibrated_score is reported separately and is not mixed into final_score"
    assert first["ablation_scores"]["full"] == first["final_score"]
    assert first["ablation_scores"]["static_baseline"] == first["static_baseline_score"]
    assert first["ablation_scores"]["learned_calibrator"] == first["calibrated_score"]
    assert first["calibration"]["mode"] == "learned_logistic"
    assert REQUIRED_CALIBRATION_FEATURES <= set(first["calibration"]["features"])


def test_calibration_smoke_report_compares_against_static_baseline() -> None:
    from services.evaluation.calibration import build_calibration_smoke_report

    report = build_calibration_smoke_report()

    assert report["dataset"] == "synthetic_calibration_smoke_v1"
    assert report["baseline"] == "static_weighted_hybrid"
    assert report["calibrator"]["mode"] == "learned_logistic"
    assert REQUIRED_CALIBRATION_FEATURES <= set(report["calibrator"]["feature_names"])
    assert report["metrics"]["calibrated_ndcg_at_3"] > report["metrics"]["static_baseline_ndcg_at_3"]
