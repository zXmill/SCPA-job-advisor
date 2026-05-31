"""Run the local SCPA scraping + ML + metrics pipeline end to end."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.retrain_models import run_retraining
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR, load_sample_dataset, validate_sample_dataset
from services.dqn.main import LearningPathRequest, OnlineDQN, RewardUpdateRequest, learning_path
from services.evaluation.recommendation_metrics import (
    catalog_coverage,
    ctr_proxy,
    fairness_gap_tpr_at_k,
    intra_list_diversity,
    p95_latency_ms,
    ranking_report,
)
from services.ncf.main import CandidateJob, OnlineNCF
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.sbert.main import sbert_score
from services.scraper.main import app as scraper_app


DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"
DEFAULT_ARTIFACT_DIR = DEFAULT_REPORTS_DIR / "full_pipeline_artifacts"
POSITIVE_LABEL_THRESHOLD = 0.7


def _stable_job_id(title: str, company: str, location: str) -> str:
    raw = f"{title.lower()}|{company.lower()}|{location.lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_job(raw: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Normalize a real scraper job row into the aggregator contract."""
    title = str(raw.get("title") or "").strip()
    company = str(raw.get("company") or "").strip()
    location = str(raw.get("location") or "").strip()
    job_id = str(
        raw.get("job_id")
        or raw.get("id")
        or raw.get("content_hash")
        or _stable_job_id(title, company, location)
    )
    skills = _as_list(
        raw.get("required_skills")
        or raw.get("required_skill_names")
        or raw.get("extracted_skills")
        or raw.get("extracted_skill_names")
        or raw.get("skills")
        or raw.get("tags")
    )
    tags = _as_list(raw.get("tags") or raw.get("skills"))
    return {
        "id": job_id,
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "description": str(raw.get("description") or "").strip(),
        "raw_description_html": raw.get("raw_description_html"),
        "description_text": str(raw.get("description_text") or raw.get("description") or "").strip(),
        "description_sections": raw.get("description_sections") or {},
        "responsibilities": _as_list(raw.get("responsibilities")),
        "requirements": _as_list(raw.get("requirements")),
        "nice_to_have": _as_list(raw.get("nice_to_have")),
        "benefits": _as_list(raw.get("benefits")),
        "seniority_level": raw.get("seniority_level"),
        "employment_type": raw.get("employment_type"),
        "job_function": raw.get("job_function"),
        "industry": raw.get("industry"),
        "education_level": raw.get("education_level"),
        "years_experience_min": raw.get("years_experience_min"),
        "years_experience_max": raw.get("years_experience_max"),
        "required_skills": _as_list(raw.get("required_skills") or raw.get("required_skill_names")),
        "preferred_skills": _as_list(raw.get("preferred_skills") or raw.get("preferred_skill_names")),
        "extracted_skills": _as_list(raw.get("extracted_skills") or raw.get("extracted_skill_names")),
        "source": str(raw.get("source") or source),
        "source_url": str(raw.get("source_url") or "").strip(),
        "source_updated_at": raw.get("source_updated_at"),
        "company_logo": raw.get("company_logo"),
        "skills": skills,
        "tags": tags,
        "is_active": bool(raw.get("is_active", True)),
    }


def validate_pipeline_jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, job in enumerate(jobs):
        prefix = f"job[{index}]"
        for field in ("job_id", "title", "company", "location", "description", "source_url"):
            if not job.get(field):
                errors.append(f"{prefix} missing {field}")
        if not job.get("company_logo"):
            warnings.append(f"{prefix} missing optional company_logo")
        if not job.get("skills") and not job.get("tags"):
            warnings.append(f"{prefix} missing optional skills/tags")
        job_id = str(job.get("job_id") or "")
        if job_id in seen:
            errors.append(f"duplicate job_id {job_id}")
        seen.add(job_id)
    return {"errors": errors, "warnings": warnings}


async def fetch_scraped_jobs(limit: int) -> dict[str, Any]:
    try:
        async with AsyncClient(transport=ASGITransport(app=scraper_app), base_url="http://scraper") as client:
            response = await client.post("/scrape/run", params={"limit": limit})
            response.raise_for_status()
        payload = response.json()
        jobs = [normalize_job(job, source="scraper") for job in payload.get("jobs", [])[:limit]]
        validation = validate_pipeline_jobs(jobs)
        return {
            "status": "ok",
            "count": len(jobs),
            "deduplicated": int(payload.get("deduplicated") or 0),
            "jobs": jobs,
            "validation": validation,
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "status": "failed",
            "count": 0,
            "deduplicated": 0,
            "jobs": [],
            "validation": {"errors": [str(exc)], "warnings": []},
        }


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("location") or ""),
            str(job.get("description") or ""),
            " ".join(_as_list(job.get("skills") or job.get("tags"))),
        ]
    )


def _positive_job_ids(interactions: list[dict[str, Any]]) -> dict[str, set[str]]:
    relevant: dict[str, set[str]] = defaultdict(set)
    for row in interactions:
        if float(row.get("label") or 0.0) >= POSITIVE_LABEL_THRESHOLD:
            relevant[str(row["user_id"])].add(str(row["job_id"]))
    return relevant


def _interaction_counts(interactions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in interactions:
        counts[str(row.get("user_id"))] += 1
    return counts


def _load_ncf_model(artifact_dir: Path, jobs: list[dict[str, Any]]) -> tuple[OnlineNCF, str]:
    artifact = artifact_dir / "ncf" / "online_ncf.json"
    model = OnlineNCF(model_path=artifact, autosave=False, load_existing=artifact.exists())
    model.upsert_jobs(
        [
            CandidateJob(
                id=str(job["job_id"]),
                title=str(job.get("title") or ""),
                description=str(job.get("description") or ""),
                tags=_as_list(job.get("skills") or job.get("tags")),
            )
            for job in jobs
        ]
    )
    return model, str(artifact)


def _train_dqn_online_agent(
    dataset: dict[str, list[dict[str, Any]]],
    jobs: list[dict[str, Any]],
    model_path: Path,
) -> OnlineDQN:
    agent = OnlineDQN(model_path=model_path, autosave=True, load_existing=False)
    agent.upsert_jobs(jobs)
    jobs_by_id = {str(job["job_id"]): job for job in jobs}
    counts = _interaction_counts(dataset["interactions"])
    for row in dataset["interactions"]:
        job = jobs_by_id.get(str(row["job_id"]))
        if not job:
            continue
        agent.learn(
            RewardUpdateRequest(
                user_id=str(row["user_id"]),
                job_id=str(row["job_id"]),
                event=str(row.get("event") or "view"),
                reward=float(row.get("label") or 0.0),
                job=job,
                state={"interaction_count": counts[str(row["user_id"])]},
                done=False,
            )
        )
    return agent


def _explanation(
    user: dict[str, Any],
    job: dict[str, Any],
    interaction_count: int,
    next_milestone: str | None = None,
) -> list[str]:
    user_skills = {str(skill).lower() for skill in _as_list(user.get("skills"))}
    job_skills = {str(skill).lower() for skill in _as_list(job.get("skills") or job.get("tags"))}
    matched = sorted(user_skills & job_skills)
    reasons = []
    if matched:
        reasons.append(f"matched skills: {', '.join(matched[:4])}")
    reasons.append(f"SBERT semantic similarity {float(job.get('sbert_score') or 0.0):.3f}")
    reasons.append(f"NCF behavior score {float(job.get('ncf_score') or 0.0):.3f}")
    reasons.append(f"DQN rerank signal {float(job.get('dqn_score') or 0.0):.3f}")
    if next_milestone:
        reasons.append(f"DQN next career milestone: {next_milestone}")
    if interaction_count == 0:
        reasons.append("cold-start fallback weighted SBERT highest")
    return reasons


async def _career_path(user: dict[str, Any]) -> dict[str, Any]:
    response = await learning_path(
        LearningPathRequest(
            user_id=str(user["user_id"]),
            current_skills=_as_list(user.get("skills")),
            target_role=str(user.get("target_role") or "Data Scientist"),
        )
    )
    return {
        "target_role": response["target_role"],
        "career_milestones": response["learning_path"],
        "explanation": "DQN ranks adaptive career milestones from the user's current skills and target role.",
        "model_version": response["model_version"],
    }


async def _score_all_users(
    dataset: dict[str, list[dict[str, Any]]],
    jobs: list[dict[str, Any]],
    artifact_dir: Path,
    top_n: int,
) -> dict[str, Any]:
    ncf_model, ncf_artifact = _load_ncf_model(artifact_dir, jobs)
    dqn_online_artifact = artifact_dir / "dqn" / "online_dqn.json"
    dqn_agent = _train_dqn_online_agent(dataset, jobs, dqn_online_artifact)
    counts = _interaction_counts(dataset["interactions"])

    rankings: dict[str, dict[str, list[str]]] = {
        "SBERT only": {},
        "NCF only": {},
        "DQN job rerank signal": {},
        "Hybrid / aggregation": {},
    }
    recommendations: dict[str, Any] = {}
    latencies_ms: dict[str, list[float]] = defaultdict(list)
    fallback_events: list[str] = []

    for user in dataset["users"]:
        user_id = str(user["user_id"])
        profile_text = str(user.get("profile_text") or "")
        interaction_count = counts[user_id]
        started_total = time.perf_counter()

        scored_jobs: list[dict[str, Any]] = []
        for job in jobs:
            scored = dict(job)
            started = time.perf_counter()
            scored["sbert_score"] = sbert_score(profile_text, _job_text(job))
            latencies_ms["SBERT only"].append((time.perf_counter() - started) * 1000)
            try:
                started = time.perf_counter()
                scored["ncf_score"] = ncf_model.predict_one(
                    user_id,
                    str(job["job_id"]),
                    profile_text=profile_text,
                )
                latencies_ms["NCF only"].append((time.perf_counter() - started) * 1000)
            except Exception as exc:  # pylint: disable=broad-except
                scored["ncf_score"] = 0.0
                fallback_events.append(f"ncf fallback for {user_id}/{job['job_id']}: {exc}")
            scored_jobs.append(scored)

        rankings["SBERT only"][user_id] = [
            str(job["job_id"]) for job in sorted(scored_jobs, key=lambda item: item["sbert_score"], reverse=True)
        ]
        rankings["NCF only"][user_id] = [
            str(job["job_id"]) for job in sorted(scored_jobs, key=lambda item: item["ncf_score"], reverse=True)
        ]

        try:
            started = time.perf_counter()
            dqn_ranked = dqn_agent.rank(user_id, scored_jobs, {"interaction_count": interaction_count})
            latencies_ms["DQN job rerank signal"].append((time.perf_counter() - started) * 1000)
            dqn_scores = {str(row["job"]["job_id"]): float(row["q_value"]) for row in dqn_ranked}
        except Exception as exc:  # pylint: disable=broad-except
            fallback_events.append(f"dqn fallback for {user_id}: {exc}")
            dqn_ranked = [{"job": job, "q_value": 0.0} for job in scored_jobs]
            dqn_scores = {str(job["job_id"]): 0.0 for job in scored_jobs}

        rankings["DQN job rerank signal"][user_id] = [str(row["job"]["job_id"]) for row in dqn_ranked]
        for job in scored_jobs:
            job["dqn_score"] = dqn_scores.get(str(job["job_id"]), 0.0)

        aggregate_user = {
            "id": user_id,
            "interaction_count": interaction_count,
            "profile_text": profile_text,
        }
        aggregated = await run_aggregate_stage(aggregate_user, scored_jobs)
        latencies_ms["Hybrid / aggregation"].append((time.perf_counter() - started_total) * 1000)
        rankings["Hybrid / aggregation"][user_id] = [str(job["job_id"]) for job in aggregated.ranked]
        career = await _career_path(user)
        first_milestone = None
        if career["career_milestones"]:
            first = career["career_milestones"][0]
            first_milestone = str(first.get("title") or first.get("skill") or first.get("step_id") or "")
        top_jobs = []
        for job in aggregated.ranked[:top_n]:
            top_jobs.append(
                {
                    "job_id": str(job["job_id"]),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "company_logo": job.get("company_logo"),
                    "location": job.get("location"),
                    "source_url": job.get("source_url"),
                    "final_score": float(job["final_score"]),
                    "sbert_score": float(job["sbert_score"]),
                    "ncf_score": float(job["ncf_score"]),
                    "dqn_score": float(job["dqn_score"]),
                    "weights": job["weights"],
                    "explanation": _explanation(user, job, interaction_count, first_milestone),
                }
            )
        recommendations[user_id] = {
            "user_id": user_id,
            "job_recommendations": top_jobs,
            "career_path": career,
            "scores": {
                "top_final_score": top_jobs[0]["final_score"] if top_jobs else 0.0,
                "recommendation_count": len(top_jobs),
            },
        }

    return {
        "rankings": rankings,
        "recommendations": recommendations,
        "latencies_ms": {key: p95_latency_ms(values) for key, values in latencies_ms.items()},
        "fallback_events": fallback_events,
        "artifacts": {
            "ncf": ncf_artifact,
            "dqn_online": str(dqn_online_artifact),
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _metric_rows(
    rankings: dict[str, dict[str, list[str]]],
    relevant_by_user: dict[str, set[str]],
    interactions: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    users: list[dict[str, Any]],
    latencies_ms: dict[str, float],
) -> list[dict[str, Any]]:
    catalog_ids = {str(job["job_id"]) for job in jobs}
    item_features = {str(job["job_id"]): _as_list(job.get("skills") or job.get("tags")) for job in jobs}
    group_by_user = {str(user["user_id"]): str(user.get("demographic_group") or "unknown") for user in users}
    rows: list[dict[str, Any]] = []
    for model_name, model_rankings in rankings.items():
        row = {"model": model_name, **ranking_report(model_rankings, relevant_by_user, k_values=(5, 10))}
        row["ctr_proxy"] = ctr_proxy(interactions)
        row["catalog_coverage_at_5"] = catalog_coverage(model_rankings, catalog_ids, k=5)
        row["intra_list_diversity_at_5"] = intra_list_diversity(model_rankings, item_features, k=5)
        fairness = fairness_gap_tpr_at_k(model_rankings, relevant_by_user, group_by_user, k=5)
        row["fairness_gap_pp_at_5"] = fairness["fairness_gap_pp"]
        row["latency_p95_ms"] = latencies_ms.get(model_name, 0.0)
        rows.append({key: round(value, 6) if isinstance(value, float) else value for key, value in row.items()})
    return rows


async def run_full_pipeline(
    *,
    sample_dir: Path = DEFAULT_SAMPLE_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    steps: int = 2,
    limit: int = 5,
    skip_retraining: bool = False,
    skip_scraper: bool = False,
) -> dict[str, Any]:
    dataset = load_sample_dataset(sample_dir)
    dataset_errors = validate_sample_dataset(dataset)
    if skip_scraper:
        scraped = {
            "status": "skipped",
            "count": 0,
            "deduplicated": 0,
            "jobs": [],
            "validation": {
                "errors": [],
                "warnings": ["scraper skipped; no runtime sample jobs used"],
            },
        }
    else:
        scraped = await fetch_scraped_jobs(limit=max(limit, 10))
    jobs = scraped["jobs"]

    if not dataset["users"] or not jobs:
        report_csv = reports_dir / "full_pipeline_metrics.csv"
        summary_json = reports_dir / "full_pipeline_summary.json"
        recommendations_json = reports_dir / "full_pipeline_recommendations.json"
        summary = {
            "status": "empty_input",
            "dataset": {"counts": {key: len(value) for key, value in dataset.items()}, "validation_errors": dataset_errors},
            "scraper": {key: value for key, value in scraped.items() if key != "jobs"},
            "candidate_jobs": {
                "sample_jobs": 0,
                "scraped_jobs": scraped["count"],
                "merged_jobs": 0,
                "validation": validate_pipeline_jobs([]),
            },
            "recommendations": {},
            "metrics": [],
            "reports": {
                "metrics_csv": str(report_csv),
                "summary_json": str(summary_json),
                "recommendations_json": str(recommendations_json),
            },
        }
        _write_json(summary_json, summary)
        _write_json(recommendations_json, {})
        _write_csv(report_csv, [])
        return summary

    retraining_result: dict[str, Any]
    if skip_retraining:
        retraining_result = {"status": "skipped", "output_dir": str(artifact_dir)}
    else:
        retraining_result = run_retraining(sample_dir, artifact_dir, steps=steps)

    scored = await _score_all_users(dataset, jobs, artifact_dir, top_n=limit)
    relevant_by_user = _positive_job_ids(dataset["interactions"])
    metric_rows = _metric_rows(
        scored["rankings"],
        relevant_by_user,
        dataset["interactions"],
        jobs,
        dataset["users"],
        scored["latencies_ms"],
    )
    report_csv = reports_dir / "full_pipeline_metrics.csv"
    summary_json = reports_dir / "full_pipeline_summary.json"
    recommendations_json = reports_dir / "full_pipeline_recommendations.json"

    _write_csv(report_csv, metric_rows)
    _write_json(recommendations_json, scored["recommendations"])

    status = "ok"
    blockers = []
    if dataset_errors or scraped["validation"]["errors"]:
        status = "check"
        blockers.extend(dataset_errors)
        blockers.extend(scraped["validation"]["errors"])
    if not any(payload["job_recommendations"] for payload in scored["recommendations"].values()):
        status = "failed"
        blockers.append("no job recommendations generated")

    summary = {
        "status": status,
        "blockers": blockers,
        "dataset": {
            "sample_dir": str(sample_dir),
            "counts": {key: len(value) for key, value in dataset.items()},
            "validation_errors": dataset_errors,
        },
        "scraper": {key: value for key, value in scraped.items() if key != "jobs"},
        "candidate_jobs": {
            "sample_jobs": 0,
            "scraped_jobs": scraped["count"],
            "merged_jobs": len(jobs),
            "validation": validate_pipeline_jobs(jobs),
        },
        "retraining": retraining_result,
        "artifacts": scored["artifacts"],
        "metrics": metric_rows,
        "reports": {
            "metrics_csv": str(report_csv),
            "summary_json": str(summary_json),
            "recommendations_json": str(recommendations_json),
        },
        "recommendations": scored["recommendations"],
        "fallback_events": scored["fallback_events"],
    }
    _write_json(summary_json, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SCPA full local pipeline validation.")
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--limit", type=int, default=5)
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
        )
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "dataset": summary.get("dataset"),
                "scraper": summary.get("scraper"),
                "reports": summary.get("reports"),
                "blockers": summary.get("blockers", []),
            },
            indent=2,
        )
    )
    return 0 if summary["status"] in {"ok", "check"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
