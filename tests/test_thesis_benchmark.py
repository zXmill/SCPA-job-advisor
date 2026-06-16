"""Tests for the thesis benchmark: grounded simulator + leak-free splits.

These guard the two properties an examiner attacks first: (1) the simulated
data is reproducible and grounded, and (2) the splits do not leak. Model
training (torch) is intentionally not exercised here so the suite stays fast.
"""

from __future__ import annotations

import pytest

from services.evaluation.synthetic_behavior import (
    compute_affinity,
    generate_behavior_benchmark,
)
from services.evaluation.splits import (
    assert_no_leakage,
    leave_one_out_split,
    relevant_by_user,
    session_split,
    temporal_split,
    user_holdout_split,
)


PROFILES = [
    {
        "profile_id": f"p-{i:03d}",
        "domain": "software_development" if i % 2 == 0 else "data_ai",
        "occupation_group": "backend" if i % 2 == 0 else "data_analysis",
        "skills": ["python", "sql", "backend"] if i % 2 == 0 else ["python", "statistics", "ml"],
        "profile_text": f"profile {i}",
    }
    for i in range(40)
]
JOBS = [
    {
        "job_id": f"j-{i:03d}",
        "title": f"Job {i}",
        "domain": "software_development" if i % 2 == 0 else "data_ai",
        "occupation_group": "backend" if i % 2 == 0 else "data_analysis",
        "required_skills": ["python", "backend"] if i % 2 == 0 else ["python", "statistics"],
        "preferred_skills": ["sql"],
    }
    for i in range(60)
]


def _benchmark():
    return generate_behavior_benchmark(
        PROFILES, JOBS, n_users=30, candidate_pool_size=20, sessions_per_user=2, seed=7
    )


# --- affinity -------------------------------------------------------------- #

def test_affinity_is_bounded_unit_interval():
    for profile in PROFILES:
        for job in JOBS:
            value = compute_affinity(profile, job)
            assert 0.0 <= value <= 1.0


def test_affinity_rewards_matching_attributes():
    matched = compute_affinity(PROFILES[0], JOBS[0])  # same domain/occ/skill overlap
    mismatched = compute_affinity(PROFILES[0], JOBS[1])  # different domain/occ
    assert matched > mismatched


# --- simulator ------------------------------------------------------------- #

def test_simulator_is_deterministic_for_same_seed():
    a = generate_behavior_benchmark(PROFILES, JOBS, n_users=20, seed=99)
    b = generate_behavior_benchmark(PROFILES, JOBS, n_users=20, seed=99)
    assert a.interactions == b.interactions
    assert a.sessions == b.sessions


def test_simulator_changes_with_seed():
    a = generate_behavior_benchmark(PROFILES, JOBS, n_users=20, seed=1)
    b = generate_behavior_benchmark(PROFILES, JOBS, n_users=20, seed=2)
    assert a.interactions != b.interactions


def test_simulator_stamps_simulated_provenance():
    bench = _benchmark()
    assert bench.metadata["provenance"] == "simulated_grounded"
    assert all(row["provenance"] == "simulated_grounded" for row in bench.interactions)
    assert bench.metadata["n_interactions"] == len(bench.interactions)


def test_simulator_produces_positive_and_negative_events():
    bench = _benchmark()
    labels = {row["label"] for row in bench.interactions}
    assert labels == {0, 1}, "benchmark must contain both positive and negative interactions"


# --- splits: leakage guarantees ------------------------------------------- #

def test_temporal_split_orders_test_after_train():
    bench = _benchmark()
    split = temporal_split(bench.interactions)
    assert split.leakage_report["ordering_holds"] is True
    assert_no_leakage(split)


def test_temporal_split_contains_returning_users_after_interleaved_schedule():
    bench = _benchmark()
    split = temporal_split(bench.interactions)
    train_users = {r["user_id"] for r in split.train}
    test_users = {r["user_id"] for r in split.test}

    assert bench.metadata["temporal_schedule"] == "interleaved_user_waves"
    assert len(test_users) >= 4
    assert test_users.issubset(train_users)
    assert split.leakage_report["cold_users_in_test"] == 0


def test_user_holdout_has_no_user_overlap():
    bench = _benchmark()
    split = user_holdout_split(bench.interactions, seed=7)
    train_users = {r["user_id"] for r in split.train}
    test_users = {r["user_id"] for r in split.test}
    assert train_users.isdisjoint(test_users)
    assert split.leakage_report["user_overlap_holds"] is True
    assert_no_leakage(split)


def test_session_split_keeps_sessions_intact():
    bench = _benchmark()
    split = session_split(bench.sessions)
    train_ids = {s["session_id"] for s in split.train}
    test_ids = {s["session_id"] for s in split.test}
    assert train_ids.isdisjoint(test_ids)
    assert_no_leakage(split)


def test_leave_one_out_holds_one_per_user():
    bench = _benchmark()
    split = leave_one_out_split(bench.interactions)
    # Every test row's user must also appear in train (earlier interactions).
    train_users = {r["user_id"] for r in split.train}
    for row in split.test:
        assert row["user_id"] in train_users


def test_assert_no_leakage_raises_on_violation():
    from services.evaluation.splits import SplitResult

    bad = SplitResult(
        strategy="user_holdout",
        train=[{"user_id": "u1", "job_id": "j1"}],
        validation=[],
        test=[{"user_id": "u1", "job_id": "j2"}],
        leakage_report={"user_overlap_holds": False},
    )
    with pytest.raises(AssertionError):
        assert_no_leakage(bad)


# --- ground truth construction -------------------------------------------- #

def test_relevant_by_user_binary_and_graded():
    rows = [
        {"user_id": "u1", "job_id": "j1", "label": 1, "relevance_grade": 3.0},
        {"user_id": "u1", "job_id": "j2", "label": 0, "relevance_grade": 0.0},
        {"user_id": "u2", "job_id": "j3", "label": 1, "relevance_grade": 2.0},
    ]
    binary = relevant_by_user(rows, graded=False)
    graded = relevant_by_user(rows, graded=True)
    assert binary == {"u1": {"j1"}, "u2": {"j3"}}
    assert graded == {"u1": {"j1": 3.0}, "u2": {"j3": 2.0}}
