"""Retrain SCPA local models from sample or scraped job/interaction data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.dqn.training.train_dqn import train as train_dqn
from services.ncf.main import CandidateJob, OnlineNCF
from services.sbert.training.train_sbert import train_from_pairs

from scripts.evaluate_sample_pipeline import evaluate
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR, load_sample_dataset


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("description") or ""),
            " ".join(map(str, job.get("skills") or [])),
        ]
    ).strip()


def _train_sbert_from_sample(dataset: dict[str, list[dict[str, Any]]], output_dir: Path, steps: int) -> dict[str, Any]:
    users = {user["user_id"]: user for user in dataset["users"]}
    jobs = {job["job_id"]: job for job in dataset["jobs"]}
    pairs = []
    for row in dataset["interactions"]:
        if float(row.get("label") or 0.0) >= 0.7:
            pairs.append((users[row["user_id"]]["profile_text"], _job_text(jobs[row["job_id"]])))
    return train_from_pairs(pairs, output_dir, steps=steps)


def _train_online_ncf_from_sample(dataset: dict[str, list[dict[str, Any]]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "online_ncf.json"
    model = OnlineNCF(model_path=artifact, autosave=True, load_existing=False)
    model.upsert_jobs(
        [
            CandidateJob(
                id=job["job_id"],
                title=job["title"],
                description=job["description"],
                tags=job.get("skills") or [],
            )
            for job in dataset["jobs"]
        ]
    )
    users = {user["user_id"]: user for user in dataset["users"]}
    losses = []
    for _ in range(8):
        for row in dataset["interactions"]:
            losses.append(
                model.learn_one(
                    row["user_id"],
                    row["job_id"],
                    float(row.get("label") or 0.0),
                    profile_text=users[row["user_id"]].get("profile_text"),
                )
            )
    model.save()
    return {
        "checkpoint": str(artifact),
        "feedback_events": model.feedback_events,
        "items": len(model.item_factors),
        "users": len(model.user_factors),
        "mean_absolute_error": round(sum(losses) / max(len(losses), 1), 6),
    }


def run_retraining(sample_dir: Path, output_dir: Path, steps: int = 4) -> dict[str, Any]:
    dataset = load_sample_dataset(sample_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"output_dir": str(output_dir), "models": {}}

    stages = {
        "sbert": lambda: _train_sbert_from_sample(dataset, output_dir / "sbert", steps),
        "ncf": lambda: _train_online_ncf_from_sample(dataset, output_dir / "ncf"),
        "dqn": lambda: train_dqn(output_dir / "dqn", steps=steps),
    }
    for name, fn in stages.items():
        try:
            result["models"][name] = {"status": "trained", **fn()}
        except Exception as exc:  # pylint: disable=broad-except
            result["models"][name] = {"status": "failed", "error": str(exc)}

    try:
        evaluation = evaluate(dataset)
        result["evaluation"] = evaluation
        result["status"] = "ok" if evaluation["ready"] else "check"
    except Exception as exc:  # pylint: disable=broad-except
        result["status"] = "failed"
        result["evaluation_error"] = str(exc)

    manifest = output_dir / "retraining_manifest.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["manifest"] = str(manifest)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=4)
    args = parser.parse_args()
    result = run_retraining(args.sample_dir, args.output_dir, steps=args.steps)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"ok", "check"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
