"""Thesis evidence classification and evaluation protocol for SCPA.

The protocol is intentionally conservative: small/demo datasets are reported as
insufficient, and smoke/proxy baselines are never marked as thesis evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any

from services.evaluation.ablation import evaluate_ablation
from services.evaluation.significance import compare_paired


MIN_PRELIMINARY_USERS = 30
MIN_PRELIMINARY_JOBS = 100
MIN_PRELIMINARY_INTERACTIONS = 300
SMOKE_BASELINE_TYPE = "deterministic_smoke_proxy"
METRICS = ["precision_at_k", "recall_at_k", "ndcg_at_k", "hit_rate_at_k"]


def classify_evidence_quality(
    *,
    users_count: int,
    jobs_count: int,
    interactions_count: int,
    baseline_type: str = "none",
    baseline_is_mock: bool = False,
) -> dict[str, Any]:
    blockers: list[str] = []
    if users_count < MIN_PRELIMINARY_USERS:
        blockers.append(f"users_count {users_count} < minimum {MIN_PRELIMINARY_USERS}")
    if jobs_count < MIN_PRELIMINARY_JOBS:
        blockers.append(f"jobs_count {jobs_count} < minimum {MIN_PRELIMINARY_JOBS}")
    if interactions_count < MIN_PRELIMINARY_INTERACTIONS:
        blockers.append(
            f"interactions_count {interactions_count} < minimum {MIN_PRELIMINARY_INTERACTIONS}"
        )

    dataset_status = (
        "sufficient_for_preliminary_evaluation"
        if not blockers
        else "insufficient_for_generalization"
    )
    baseline_is_valid_for_thesis = not baseline_is_mock and not blockers
    evidence_type = (
        "real_evaluation"
        if baseline_is_valid_for_thesis
        else "smoke_test_only"
        if baseline_is_mock
        else "demo_sample_only"
    )
    limitations = []
    if blockers:
        limitations.append("Dataset is below preliminary thesis-evidence thresholds.")
    if baseline_is_mock:
        limitations.append("Baseline is a deterministic smoke proxy, not a trained thesis baseline.")

    return {
        "evidence_type": evidence_type,
        "dataset_status": dataset_status,
        "users_count": users_count,
        "jobs_count": jobs_count,
        "interactions_count": interactions_count,
        "is_generalization_evidence": baseline_is_valid_for_thesis,
        "evaluation_blockers": blockers,
        "baseline_type": baseline_type,
        "baseline_is_mock": baseline_is_mock,
        "baseline_is_valid_for_thesis": baseline_is_valid_for_thesis,
        "limitations": limitations,
        "minimum_thresholds": {
            "users": MIN_PRELIMINARY_USERS,
            "jobs": MIN_PRELIMINARY_JOBS,
            "interactions": MIN_PRELIMINARY_INTERACTIONS,
        },
    }


def _split_users(users: list[str], n_splits: int = 5, seed: int = 42) -> list[tuple[set[str], set[str]]]:
    rng = random.Random(seed)
    shuffled = users[:]
    rng.shuffle(shuffled)
    fold_size = max(1, len(shuffled) // n_splits)
    folds = [shuffled[i * fold_size : (i + 1) * fold_size] for i in range(n_splits)]
    results: list[tuple[set[str], set[str]]] = []
    for i in range(n_splits):
        test = set(folds[i])
        train = set().union(*[f for j, f in enumerate(folds) if j != i])
        results.append((train, test))
    return results


def _stable_score(*parts: Any) -> float:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _semantic_smoke_rank(
    user_id: str,
    candidates: list[dict[str, Any]],
    profile_text: str,
) -> list[str]:
    scored = [
        (candidate, _stable_score("semantic", user_id, profile_text, candidate.get("id")))
        for candidate in candidates
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [str(candidate["id"]) for candidate, _ in scored]


def _interaction_smoke_rank(
    user_id: str,
    candidates: list[dict[str, Any]],
) -> list[str]:
    scored = [
        (candidate, _stable_score("interaction", user_id, candidate.get("id")))
        for candidate in candidates
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [str(candidate["id"]) for candidate, _ in scored]


def _run_split(
    train_users: set[str],
    test_users: set[str],
    all_interactions: dict[str, list[str]],
    all_jobs: list[dict[str, Any]],
    k: int = 10,
) -> dict[str, dict[str, float]]:
    """Evaluate one smoke fold and return metric dict per variant."""
    del train_users
    relevant = {
        uid: set(all_interactions.get(uid, [])[-5:]) for uid in test_users
    }
    rankings: dict[str, dict[str, list[str]]] = {
        "sbert_only": {},
        "mf_only": {},
        "ncf_only": {},
        "dqn_only": {},
        "full_scpa": {},
    }
    for uid in test_users:
        profile = f"user profile {uid}"
        rankings["sbert_only"][uid] = _semantic_smoke_rank(uid, all_jobs, profile)
        rankings["mf_only"][uid] = _interaction_smoke_rank(uid, all_jobs)
        rankings["ncf_only"][uid] = _interaction_smoke_rank(uid, all_jobs)
        rankings["dqn_only"][uid] = _interaction_smoke_rank(uid, all_jobs)
        rankings["full_scpa"][uid] = _semantic_smoke_rank(uid, all_jobs, profile)

    results: dict[str, dict[str, float]] = {}
    for variant, ranking in rankings.items():
        report = evaluate_ablation({variant: ranking}, relevant, k=k)
        results[variant] = report.get(variant, {})
    return results


def _load_interactions(path: Path) -> dict[str, list[str]]:
    interactions: dict[str, list[str]] = {}
    if not path.exists():
        return interactions
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        row = json.loads(line)
        interactions.setdefault(str(row["user_id"]), []).append(str(row["job_id"]))
    return interactions


def _load_jobs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]


def build_evaluation_report(
    *,
    interactions: dict[str, list[str]],
    jobs: list[dict[str, Any]],
    splits: int,
    k: int,
) -> dict[str, Any]:
    users = list(interactions.keys())
    interactions_count = sum(len(values) for values in interactions.values())
    evidence_quality = classify_evidence_quality(
        users_count=len(users),
        jobs_count=len(jobs),
        interactions_count=interactions_count,
        baseline_type=SMOKE_BASELINE_TYPE,
        baseline_is_mock=True,
    )

    output: dict[str, Any] = {
        "splits": splits,
        "k": k,
        "n_users": len(users),
        "n_jobs": len(jobs),
        "n_interactions": interactions_count,
        "evidence_quality": evidence_quality,
        "dataset_status": evidence_quality["dataset_status"],
        "evidence_type": evidence_quality["evidence_type"],
        "is_generalization_evidence": evidence_quality["is_generalization_evidence"],
        "baseline_type": evidence_quality["baseline_type"],
        "baseline_is_mock": evidence_quality["baseline_is_mock"],
        "baseline_is_valid_for_thesis": evidence_quality["baseline_is_valid_for_thesis"],
        "evaluation_blockers": evidence_quality["evaluation_blockers"],
        "limitations": evidence_quality["limitations"],
        "summary": {},
        "significance": {},
        "fold_results": [],
    }
    if evidence_quality["dataset_status"] == "insufficient_for_generalization":
        output["status"] = "blocked_insufficient_evidence"
        return output

    fold_results: list[dict[str, dict[str, float]]] = []
    for train, test in _split_users(users, splits):
        fold_results.append(_run_split(train, test, interactions, jobs, k=k))

    variants = list(fold_results[0].keys()) if fold_results else []
    aggregated: dict[str, dict[str, list[float]]] = {
        variant: {metric: [] for metric in METRICS} for variant in variants
    }
    for fold in fold_results:
        for variant, vals in fold.items():
            for metric in METRICS:
                aggregated[variant][metric].append(float(vals.get(metric, 0.0)))

    summary: dict[str, Any] = {}
    for variant in variants:
        summary[variant] = {
            metric: {
                "mean": round(statistics.mean(aggregated[variant][metric]), 4),
                "stdev": round(statistics.stdev(aggregated[variant][metric]), 4)
                if len(aggregated[variant][metric]) > 1
                else 0.0,
            }
            for metric in METRICS
        }

    sig_results: dict[str, Any] = {}
    baseline = "full_scpa"
    for variant in variants:
        if variant == baseline:
            continue
        for metric in METRICS:
            base_scores = {f"fold_{i}": fold[baseline].get(metric, 0.0) for i, fold in enumerate(fold_results)}
            var_scores = {f"fold_{i}": fold[variant].get(metric, 0.0) for i, fold in enumerate(fold_results)}
            sig_results[f"{variant}_vs_{baseline}_{metric}"] = compare_paired(
                var_scores,
                base_scores,
                alpha=0.05,
            )

    output.update(
        {
            "status": "smoke_metrics_only",
            "summary": summary,
            "significance": sig_results,
            "fold_results": [
                {variant: {metric: round(fold[variant].get(metric, 0.0), 4) for metric in METRICS} for variant in variants}
                for fold in fold_results
            ],
        }
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="SCPA thesis evaluation protocol")
    parser.add_argument("--interactions", type=Path, default=Path("data/interactions.jsonl"))
    parser.add_argument("--jobs", type=Path, default=Path("data/jobs.jsonl"))
    parser.add_argument("--splits", type=int, default=5)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("reports/thesis_evaluation.json"))
    args = parser.parse_args()

    report = build_evaluation_report(
        interactions=_load_interactions(args.interactions),
        jobs=_load_jobs(args.jobs),
        splits=args.splits,
        k=args.k,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Evaluation report written to {args.output}")
    if report["status"] == "blocked_insufficient_evidence":
        print("Evaluation blocked: dataset is insufficient for generalization evidence.")


if __name__ == "__main__":
    main()
