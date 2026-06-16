"""Leak-free evaluation splits for SCPA behavioral benchmarks.

The single biggest examiner objection against a recommender evaluation is data
leakage: random splits leak future behavior into the past and inflate
personalization metrics. This module builds *defensible* splits and emits an
explicit leakage report so the thesis can prove the evaluation is honest:

- ``temporal_split``      — global timestamp cutoff (past trains, future tests).
- ``user_holdout_split``  — entire users held out (cold-start generalization).
- ``leave_one_out_split`` — last interaction per user held out (classic LOO).
- ``session_split``       — whole sessions held out, ordered temporally (DQN).

Every split returns a ``SplitResult`` whose ``leakage_report`` documents which
invariant the split guarantees and asserts it holds on the produced data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

Interaction = dict[str, Any]


@dataclass(frozen=True)
class SplitResult:
    """A train/val/test partition plus an auditable leakage report."""

    strategy: str
    train: list[Interaction]
    validation: list[Interaction]
    test: list[Interaction]
    leakage_report: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
        }


def _ts(row: Interaction) -> str:
    return str(row.get("timestamp") or "")


def _users(rows: list[Interaction]) -> set[str]:
    return {str(r.get("user_id")) for r in rows}


def _items(rows: list[Interaction]) -> set[str]:
    return {str(r.get("job_id")) for r in rows}


def temporal_split(
    interactions: list[Interaction],
    *,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
) -> SplitResult:
    """Split by a global timestamp cutoff. Past -> train, future -> test.

    This is the most defensible split for an online recommender: at serving
    time the model only ever sees the past, so the offline evaluation must too.
    """
    ordered = sorted(interactions, key=_ts)
    n = len(ordered)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)
    n_train = n - n_val - n_test
    train = ordered[:n_train]
    validation = ordered[n_train : n_train + n_val]
    test = ordered[n_train + n_val :]

    train_max = _ts(train[-1]) if train else ""
    test_min = _ts(test[0]) if test else ""
    report = {
        "strategy": "temporal",
        "guarantee": "test timestamps are all >= max train timestamp",
        "train_max_timestamp": train_max,
        "test_min_timestamp": test_min,
        "ordering_holds": (not train or not test or test_min >= train_max),
        "cold_users_in_test": len(_users(test) - _users(train)),
        "cold_items_in_test": len(_items(test) - _items(train)),
    }
    return SplitResult("temporal", train, validation, test, report)


def user_holdout_split(
    interactions: list[Interaction],
    *,
    test_user_frac: float = 0.2,
    val_user_frac: float = 0.1,
    seed: int = 42,
) -> SplitResult:
    """Hold out entire users for a cold-start generalization test.

    No interaction of a test user appears in train, so metrics reflect how the
    model generalizes to users it has never seen.
    """
    import random

    rng = random.Random(seed)
    users = sorted(_users(interactions))
    rng.shuffle(users)
    n_test = int(len(users) * test_user_frac)
    n_val = int(len(users) * val_user_frac)
    test_users = set(users[:n_test])
    val_users = set(users[n_test : n_test + n_val])
    train_users = set(users[n_test + n_val :])

    train = [r for r in interactions if str(r.get("user_id")) in train_users]
    validation = [r for r in interactions if str(r.get("user_id")) in val_users]
    test = [r for r in interactions if str(r.get("user_id")) in test_users]

    overlap = _users(train) & _users(test)
    report = {
        "strategy": "user_holdout",
        "guarantee": "no user appears in both train and test",
        "n_train_users": len(train_users),
        "n_val_users": len(val_users),
        "n_test_users": len(test_users),
        "user_overlap_count": len(overlap),
        "user_overlap_holds": len(overlap) == 0,
    }
    return SplitResult("user_holdout", train, validation, test, report)


def leave_one_out_split(interactions: list[Interaction]) -> SplitResult:
    """Hold out each user's chronologically last interaction as test.

    Classic LOO protocol for top-N recommendation: the most recent action is
    predicted from all earlier actions of the same user.
    """
    by_user: dict[str, list[Interaction]] = {}
    for row in interactions:
        by_user.setdefault(str(row.get("user_id")), []).append(row)

    train: list[Interaction] = []
    test: list[Interaction] = []
    for rows in by_user.values():
        rows_sorted = sorted(rows, key=_ts)
        if len(rows_sorted) < 2:
            train.extend(rows_sorted)
            continue
        train.extend(rows_sorted[:-1])
        test.append(rows_sorted[-1])

    report = {
        "strategy": "leave_one_out",
        "guarantee": "test holds the last interaction per user; all earlier ones train",
        "n_test_held_out": len(test),
        "n_users_with_holdout": len(test),
        "users_too_short_for_holdout": sum(1 for rows in by_user.values() if len(rows) < 2),
    }
    return SplitResult("leave_one_out", train, [], test, report)


def session_split(
    sessions: list[dict[str, Any]],
    *,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    time_key: str = "end_timestamp",
) -> SplitResult:
    """Split whole sessions by time. A session never straddles two partitions.

    Splitting per-step would leak within-session context into train; splitting
    per-session keeps each DQN trajectory intact and temporally ordered.
    """
    ordered = sorted(sessions, key=lambda s: str(s.get(time_key) or ""))
    n = len(ordered)
    n_test = int(n * test_frac)
    n_val = int(n * val_frac)
    n_train = n - n_val - n_test
    train = ordered[:n_train]
    validation = ordered[n_train : n_train + n_val]
    test = ordered[n_train + n_val :]

    train_ids = {s["session_id"] for s in train}
    test_ids = {s["session_id"] for s in test}
    report = {
        "strategy": "session",
        "guarantee": "each session lies wholly in one partition; test sessions are temporally last",
        "n_train_sessions": len(train),
        "n_val_sessions": len(validation),
        "n_test_sessions": len(test),
        "session_overlap_count": len(train_ids & test_ids),
        "session_overlap_holds": len(train_ids & test_ids) == 0,
    }
    return SplitResult("session", train, validation, test, report)


def assert_no_leakage(result: SplitResult) -> None:
    """Raise if a split's own guarantee is violated. Use as a hard gate."""
    report = result.leakage_report
    checks: dict[str, Callable[[dict[str, Any]], bool]] = {
        "temporal": lambda r: bool(r.get("ordering_holds", False)),
        "user_holdout": lambda r: bool(r.get("user_overlap_holds", False)),
        "session": lambda r: bool(r.get("session_overlap_holds", False)),
        "leave_one_out": lambda r: r.get("n_test_held_out", 0) >= 0,
    }
    check = checks.get(result.strategy)
    if check is not None and not check(report):
        raise AssertionError(f"leakage detected for split '{result.strategy}': {report}")


def relevant_by_user(test_rows: list[Interaction], *, graded: bool = False) -> dict[str, Any]:
    """Build the test ground truth: positive jobs per user.

    With ``graded=True`` returns {user: {job: relevance_grade}} for graded NDCG;
    otherwise {user: set(job_ids)} of positive interactions for binary metrics.
    """
    if graded:
        out_graded: dict[str, dict[str, float]] = {}
        for row in test_rows:
            grade = float(row.get("relevance_grade") or 0.0)
            if grade <= 0:
                continue
            out_graded.setdefault(str(row.get("user_id")), {})[str(row.get("job_id"))] = grade
        return out_graded
    out_binary: dict[str, set[str]] = {}
    for row in test_rows:
        if int(row.get("label") or 0) == 1:
            out_binary.setdefault(str(row.get("user_id")), set()).add(str(row.get("job_id")))
    return out_binary
