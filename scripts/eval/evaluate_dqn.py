"""Evaluate DQN skill policy via offline simulation.

P5-ML-004: Run offline simulation comparing learned policy vs random baseline
on a fixed set of test scenarios. Report ranking and policy metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from services.dqn.main import OnlineDQN, RewardUpdateRequest
from services.evaluation.recommendation_metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    hit_rate_at_k,
    mean_metric,
)


def _build_test_scenarios() -> list[dict[str, Any]]:
    """Build deterministic test scenarios: user + positive job + negative job."""
    return [
        {
            "user_id": "u-test-1",
            "positive": {"id": "job-mc", "title": "Master of Ceremony", "sbert_score": 0.8, "ncf_score": 0.7},
            "negative": {"id": "job-backend", "title": "Backend Developer", "sbert_score": 0.1, "ncf_score": 0.2},
        },
        {
            "user_id": "u-test-2",
            "positive": {"id": "job-writer", "title": "Content Writer", "sbert_score": 0.75, "ncf_score": 0.65},
            "negative": {"id": "job-data", "title": "Data Scientist", "sbert_score": 0.15, "ncf_score": 0.25},
        },
        {
            "user_id": "u-test-3",
            "positive": {"id": "job-frontend", "title": "Frontend Developer", "sbert_score": 0.85, "ncf_score": 0.8},
            "negative": {"id": "job-hr", "title": "HR Specialist", "sbert_score": 0.2, "ncf_score": 0.3},
        },
    ]


def evaluate_dqn(
    output_dir: Path,
    training_steps: int = 30,
    k_values: tuple[int, ...] = (2,),
) -> dict[str, Any]:
    scenarios = _build_test_scenarios()
    agent = OnlineDQN(load_existing=False, autosave=False)

    # Pre-train agent on scenarios
    for scenario in scenarios:
        agent.upsert_jobs([scenario["positive"], scenario["negative"]])
        for _ in range(training_steps):
            agent.learn(
                RewardUpdateRequest(
                    user_id=scenario["user_id"],
                    job_id=scenario["positive"]["id"],
                    event="click",
                    job=scenario["positive"],
                )
            )
            agent.learn(
                RewardUpdateRequest(
                    user_id=scenario["user_id"],
                    job_id=scenario["negative"]["id"],
                    event="skip",
                    job=scenario["negative"],
                    done=True,
                )
            )
    agent.soft_update()

    # Evaluate policy: rank positive vs negative for each user
    rankings_policy: dict[str, list[str]] = {}
    rankings_random: dict[str, list[str]] = {}
    relevant: dict[str, set[str]] = {}

    for scenario in scenarios:
        uid = scenario["user_id"]
        jobs = [scenario["positive"], scenario["negative"]]
        policy_result = agent.rank(uid, jobs, {"interaction_count": training_steps})
        rankings_policy[uid] = [r["job"]["id"] for r in policy_result]
        # Random baseline: shuffle the same candidates
        rng = np.random.default_rng(hash(uid) % (2**31))
        shuffled = jobs.copy()
        rng.shuffle(shuffled)
        rankings_random[uid] = [j["id"] for j in shuffled]
        relevant[uid] = {scenario["positive"]["id"]}

    report: dict[str, Any] = {
        "dataset": "dqn_offline_simulation_v1",
        "n_queries": len(scenarios),
        "training_steps": training_steps,
    }

    for k in k_values:
        report[f"policy_precision_at_{k}"] = round(
            mean_metric(precision_at_k(rankings_policy[q], relevant[q], k) for q in relevant), 6
        )
        report[f"random_precision_at_{k}"] = round(
            mean_metric(precision_at_k(rankings_random[q], relevant[q], k) for q in relevant), 6
        )
        report[f"policy_ndcg_at_{k}"] = round(
            mean_metric(ndcg_at_k(rankings_policy[q], relevant[q], k) for q in relevant), 6
        )
        report[f"random_ndcg_at_{k}"] = round(
            mean_metric(ndcg_at_k(rankings_random[q], relevant[q], k) for q in relevant), 6
        )
        report[f"policy_hit_rate_at_{k}"] = round(
            mean_metric(hit_rate_at_k(rankings_policy[q], relevant[q], k) for q in relevant), 6
        )
        report[f"random_hit_rate_at_{k}"] = round(
            mean_metric(hit_rate_at_k(rankings_random[q], relevant[q], k) for q in relevant), 6
        )

    # Policy accuracy: how often does the positive job rank above negative?
    policy_wins = 0
    for scenario in scenarios:
        uid = scenario["user_id"]
        policy_ranks = rankings_policy[uid]
        pos_id = scenario["positive"]["id"]
        neg_id = scenario["negative"]["id"]
        if policy_ranks.index(pos_id) < policy_ranks.index(neg_id):
            policy_wins += 1
    report["policy_accuracy"] = round(policy_wins / len(scenarios), 6)
    report["random_accuracy"] = round(0.5, 6)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dqn_evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/dqn"))
    parser.add_argument("--training-steps", type=int, default=30)
    parser.add_argument("--k", type=int, nargs="+", default=[2])
    args = parser.parse_args()
    report = evaluate_dqn(args.output_dir, training_steps=args.training_steps, k_values=tuple(args.k))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
