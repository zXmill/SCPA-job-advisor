"""Evidence-quality contracts for thesis evaluation reporting."""

from __future__ import annotations

from services.evaluation.thesis_evaluation_protocol import (
    build_evaluation_report,
    classify_evidence_quality,
)


def test_small_dataset_is_not_generalization_evidence() -> None:
    quality = classify_evidence_quality(
        users_count=5,
        jobs_count=9,
        interactions_count=21,
        baseline_type="full_pipeline_local_run",
        baseline_is_mock=False,
    )

    assert quality["evidence_type"] == "demo_sample_only"
    assert quality["dataset_status"] == "insufficient_for_generalization"
    assert quality["is_generalization_evidence"] is False
    assert quality["baseline_is_valid_for_thesis"] is False
    assert len(quality["evaluation_blockers"]) == 3


def test_mock_baseline_is_smoke_only_even_with_large_dataset() -> None:
    quality = classify_evidence_quality(
        users_count=40,
        jobs_count=120,
        interactions_count=400,
        baseline_type="deterministic_smoke_proxy",
        baseline_is_mock=True,
    )

    assert quality["evidence_type"] == "smoke_test_only"
    assert quality["dataset_status"] == "sufficient_for_preliminary_evaluation"
    assert quality["baseline_is_mock"] is True
    assert quality["baseline_is_valid_for_thesis"] is False
    assert quality["is_generalization_evidence"] is False


def test_evaluation_report_blocks_insufficient_dataset_without_fabricated_folds() -> None:
    report = build_evaluation_report(
        interactions={"u1": ["j1"], "u2": ["j2"]},
        jobs=[{"id": "j1"}, {"id": "j2"}],
        splits=5,
        k=10,
    )

    assert report["status"] == "blocked_insufficient_evidence"
    assert report["evidence_type"] == "smoke_test_only"
    assert report["dataset_status"] == "insufficient_for_generalization"
    assert report["is_generalization_evidence"] is False
    assert report["baseline_is_mock"] is True
    assert report["baseline_is_valid_for_thesis"] is False
    assert report["fold_results"] == []
    assert report["summary"] == {}
