"""Presenter-friendly demo for the SCPA full recommendation pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_full_pipeline import DEFAULT_ARTIFACT_DIR, DEFAULT_REPORTS_DIR, run_full_pipeline
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR


def _fmt_score(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _first_user_recommendations(summary: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    recommendations = summary.get("recommendations") or {}
    for user_id, payload in recommendations.items():
        if payload.get("job_recommendations"):
            return str(user_id), payload
    return None, None


def _print_metrics(summary: dict[str, Any]) -> None:
    rows = summary.get("metrics") or []
    print("\nMetrics snapshot")
    if not rows:
        print("- no metrics generated")
        return
    for row in rows:
        model = row.get("model", "unknown")
        print(
            "- {model}: precision@5={precision}, recall@5={recall}, "
            "ndcg@5={ndcg}, hit_rate@5={hit_rate}, ctr_proxy={ctr}".format(
                model=model,
                precision=_fmt_score(row.get("precision_at_5")),
                recall=_fmt_score(row.get("recall_at_5")),
                ndcg=_fmt_score(row.get("ndcg_at_5")),
                hit_rate=_fmt_score(row.get("hit_rate_at_5")),
                ctr=_fmt_score(row.get("ctr_proxy")),
            )
        )


def _print_recommendations(user_id: str | None, payload: dict[str, Any] | None) -> None:
    print("\nJob recommendations")
    if not user_id or not payload:
        print("- no recommendations available")
        return

    print(f"User: {user_id}")
    for rank, job in enumerate(payload.get("job_recommendations", [])[:3], start=1):
        logo = job.get("company_logo") or "missing optional logo"
        print(
            "{rank}. {title} at {company} ({location}) score={score} logo={logo}".format(
                rank=rank,
                title=job.get("title") or "Untitled job",
                company=job.get("company") or "Unknown company",
                location=job.get("location") or "Unknown location",
                score=_fmt_score(job.get("final_score")),
                logo=logo,
            )
        )
        explanations = job.get("explanation") or []
        if explanations:
            print(f"   reason: {'; '.join(str(item) for item in explanations[:5])}")

    print("\nDQN reranker evidence")
    dqn_stage = payload.get("dqn_stage_contract") or {}
    if not dqn_stage:
        print("- no DQN reranker evidence available")
        return
    print(f"- mode={dqn_stage.get('dqn_mode')}")
    print(f"- candidate_pool_source={dqn_stage.get('candidate_pool_source')}")
    print(f"- evidence_type={payload.get('evidence_type')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SCPA thesis/demo pipeline.")
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--skip-retraining", action="store_true")
    parser.add_argument("--skip-scraper", action="store_true")
    args = parser.parse_args()

    summary = asyncio.run(
        run_full_pipeline(
            sample_dir=args.sample_dir,
            artifact_dir=args.artifact_dir,
            reports_dir=args.reports_dir,
            steps=args.steps,
            limit=args.limit,
            skip_retraining=args.skip_retraining,
            skip_scraper=args.skip_scraper,
            include_sample_jobs=True,
        )
    )

    print("SCPA thesis/demo pipeline")
    print(f"Demo status: {summary.get('status')}")
    print(f"Dataset: {json.dumps(summary.get('dataset', {}).get('counts', {}), sort_keys=True)}")
    print(f"Evidence: {json.dumps(summary.get('evidence_quality', {}), sort_keys=True)}")
    print(f"Scraper: {json.dumps(summary.get('scraper', {}), sort_keys=True)}")
    print(f"Reports: {json.dumps(summary.get('reports', {}), sort_keys=True)}")

    _print_metrics(summary)
    user_id, payload = _first_user_recommendations(summary)
    _print_recommendations(user_id, payload)

    blockers = summary.get("blockers") or []
    if blockers:
        print("\nBlockers")
        for blocker in blockers:
            print(f"- {blocker}")

    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
