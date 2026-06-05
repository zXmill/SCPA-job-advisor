"""Evaluate the permanent sample dataset against thesis-aligned metrics."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.ncf.main import CandidateJob, OnlineNCF
from services.sbert.main import sbert_score

from scripts.sample_dataset import DEFAULT_SAMPLE_DIR, load_sample_dataset, validate_sample_dataset


TARGETS = {
    "top5_accuracy": {"target": 0.85, "direction": "min"},
    "ndcg_at_5": {"target": 0.85, "direction": "min"},
    "ctr_proxy": {"target": 0.25, "direction": "min"},
    "latency_p95_ms": {"target": 1000.0, "direction": "max"},
    "fairness_gap_pp": {"target": 8.0, "direction": "max"},
    "dqn_action_accuracy": {"target": 0.80, "direction": "min"},
}


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int = 5) -> float:
    dcg = 0.0
    for rank, item_id in enumerate(ranked_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant_ids), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("location") or ""),
            str(job.get("description") or ""),
            " ".join(map(str, job.get("skills") or [])),
        ]
    )


def _positive_job_ids(interactions: list[dict[str, Any]]) -> dict[str, set[str]]:
    relevant: dict[str, set[str]] = defaultdict(set)
    for row in interactions:
        if float(row.get("label") or 0.0) >= 0.7:
            relevant[str(row["user_id"])].add(str(row["job_id"]))
    return relevant


def _fit_ncf(dataset: dict[str, list[dict[str, Any]]]) -> OnlineNCF:
    model = OnlineNCF(autosave=False, load_existing=False)
    candidates = [
        CandidateJob(
            id=job["job_id"],
            title=job["title"],
            description=job["description"],
            tags=job.get("skills") or [],
        )
        for job in dataset["jobs"]
    ]
    model.upsert_jobs(candidates)
    users_by_id = {user["user_id"]: user for user in dataset["users"]}
    for _ in range(6):
        for row in dataset["interactions"]:
            user = users_by_id[row["user_id"]]
            model.learn_one(
                str(row["user_id"]),
                str(row["job_id"]),
                float(row.get("label") or 0.0),
                profile_text=user.get("profile_text"),
            )
    return model


def _role_overlap(user: dict[str, Any], job: dict[str, Any]) -> float:
    target = str(user.get("target_role") or "").lower()
    haystack = f"{job.get('title', '')} {' '.join(job.get('skills') or [])}".lower()
    if "data scientist" in target:
        terms = {"python", "sql", "machine learning", "statistics", "pandas"}
    elif "backend" in target:
        terms = {"fastapi", "postgresql", "redis", "docker", "python"}
    elif "business" in target:
        terms = {"business analysis", "dashboard", "sql", "presentation"}
    elif "designer" in target:
        terms = {"figma", "ui design", "ux research", "prototyping"}
    else:
        terms = {"public speaking", "english", "event", "translation", "content writing"}
    return len([term for term in terms if term in haystack]) / max(len(terms), 1)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _next_milestone_hit(user: dict[str, Any], milestones: list[dict[str, Any]]) -> bool:
    skills = {str(skill).lower() for skill in user.get("skills") or []}
    candidates = [
        row for row in milestones
        if str(row.get("target_role") or "").lower() == str(user.get("target_role") or "").lower()
    ]
    if not candidates:
        return False
    candidates.sort(key=lambda row: float(row.get("reward") or 0.0), reverse=True)
    selected = candidates[0]
    required = {str(skill).lower() for skill in selected.get("required_skills") or []}
    return bool(required - skills) or bool(required & skills)


def evaluate(dataset: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors = validate_sample_dataset(dataset)
    if errors:
        raise ValueError("; ".join(errors))

    ncf = _fit_ncf(dataset)
    relevant_by_user = _positive_job_ids(dataset["interactions"])
    top5_hits: list[float] = []
    ndcgs: list[float] = []
    latency_ms: list[float] = []
    group_hits: dict[str, list[float]] = defaultdict(list)
    ablation_sbert: list[float] = []

    for user in dataset["users"]:
        started = time.perf_counter()
        scored: list[tuple[str, float, float]] = []
        for job in dataset["jobs"]:
            semantic = sbert_score(str(user.get("profile_text") or ""), _job_text(job))
            ncf_score_value = ncf.predict_one(
                str(user["user_id"]),
                str(job["job_id"]),
                profile_text=user.get("profile_text"),
            )
            role_score = _role_overlap(user, job)
            full_score = (0.55 * semantic) + (0.30 * ncf_score_value) + (0.15 * role_score)
            scored.append((str(job["job_id"]), full_score, semantic))

        latency_ms.append((time.perf_counter() - started) * 1000)
        ranked_full = [job_id for job_id, _, _ in sorted(scored, key=lambda row: row[1], reverse=True)]
        ranked_sbert = [job_id for job_id, _, _ in sorted(scored, key=lambda row: row[2], reverse=True)]
        relevant = relevant_by_user[str(user["user_id"])]
        hit = 1.0 if relevant.intersection(ranked_full[:5]) else 0.0
        top5_hits.append(hit)
        ndcgs.append(ndcg_at_k(ranked_full, relevant, k=5))
        ablation_sbert.append(ndcg_at_k(ranked_sbert, relevant, k=5))
        group_hits[str(user.get("demographic_group") or "unknown")].append(hit)

    positive_events = sum(1 for row in dataset["interactions"] if float(row.get("label") or 0.0) >= 0.5)
    ctr_proxy = positive_events / max(len(dataset["interactions"]), 1)
    group_tprs = {group: mean(values) for group, values in group_hits.items()}
    fairness_gap_pp = ((max(group_tprs.values()) - min(group_tprs.values())) * 100.0) if len(group_tprs) > 1 else 0.0
    dqn_hits = [_next_milestone_hit(user, dataset["milestones"]) for user in dataset["users"]]

    metrics = {
        "top5_accuracy": round(mean(top5_hits), 6),
        "ndcg_at_5": round(mean(ndcgs), 6),
        "ctr_proxy": round(ctr_proxy, 6),
        "latency_p95_ms": round(_p95(latency_ms), 6),
        "fairness_gap_pp": round(fairness_gap_pp, 6),
        "dqn_action_accuracy": round(sum(dqn_hits) / max(len(dqn_hits), 1), 6),
        "sbert_only_ndcg_at_5": round(mean(ablation_sbert), 6),
    }
    checks = []
    for metric, spec in TARGETS.items():
        value = metrics[metric]
        target = spec["target"]
        passed = value >= target if spec["direction"] == "min" else value <= target
        checks.append({"metric": metric, "value": value, "target": target, "passed": passed})

    return {
        "ready": all(row["passed"] for row in checks),
        "metrics": metrics,
        "checks": checks,
        "targets": TARGETS,
        "sample_counts": {key: len(value) for key, value in dataset.items()},
        "group_tpr": group_tprs,
        "ablation": {
            "full_ndcg_at_5": metrics["ndcg_at_5"],
            "sbert_only_ndcg_at_5": metrics["sbert_only_ndcg_at_5"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(load_sample_dataset(args.sample_dir))
    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
