"""Build the executable SCPA evaluation metrics validation notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "evaluation_metrics_validation.ipynb"


def _code(source: str) -> nbformat.NotebookNode:
    return new_code_cell(source.strip() + "\n")


def _markdown(source: str) -> nbformat.NotebookNode:
    return new_markdown_cell(source.strip() + "\n")


def build_notebook() -> nbformat.NotebookNode:
    nb = new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {
        "name": "python",
        "pygments_lexer": "ipython3",
    }

    nb.cells = [
        _markdown(
            """
# SCPA Evaluation Metrics Validation

This notebook validates the existing SCPA scraping and ML recommendation
pipeline from the permanent sample dataset through metric reports. It does not
replace service code or rebuild the project. It reuses the existing SBERT, NCF,
DQN, and aggregation paths, and it writes exportable evidence under `reports/`.

Primary outputs:

- `reports/evaluation_metrics_report.csv`
- `reports/evaluation_metrics_summary.json`
- `reports/evaluation_metrics_ranking_bars.png`
- `reports/evaluation_metrics_latency_fairness.png`
"""
        ),
        _markdown(
            """
## 1. Setup

The notebook locates the repository root, imports reusable metric helpers from
`services.evaluation.recommendation_metrics`, and creates a reports directory.
"""
        ),
        _code(
            """
from __future__ import annotations

from pathlib import Path
import json
import math
import re
import sys
import time
from statistics import mean
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pdfplumber
import torch


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "data" / "sample" / "users.jsonl").exists():
            return candidate
    raise RuntimeError("Could not locate SCPA repository root")


REPO_ROOT = find_repo_root(Path.cwd().resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REPORTS_DIR = REPO_ROOT / "reports"
ARTIFACT_DIR = REPORTS_DIR / "evaluation_artifacts"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

K_VALUES = (5, 10)
pd.set_option("display.max_columns", 80)
pd.set_option("display.width", 140)

print(f"Repo root: {REPO_ROOT}")
print(f"Reports dir: {REPORTS_DIR}")
"""
        ),
        _markdown(
            """
## Evaluation Metrics Based on TA_IBNU_SESUAI_Pedoman_Final.pdf

The thesis PDF defines SCPA as a hybrid career recommendation artifact with
NCF for collective preference, SBERT for semantic matching, and DQN for adaptive
learning-path actions. Its evaluation frame is multidimensional:

- ranking quality: Top-5 Accuracy and NDCG@5
- engagement: CTR
- usability: SUS
- technical performance: latency p95
- fairness: TPR fairness gap across demographic/program groups
- ablation: full hybrid model should outperform simplified variants

This notebook validates the code-facing subset that can be measured from the
sample data and model outputs: ranking metrics, CTR proxy, latency p95,
coverage/diversity, fairness gap, DQN action quality, and hybrid comparison.
SUS is listed as a thesis target but is not computed because no questionnaire
responses are part of the repository sample dataset.
"""
        ),
        _code(
            """
PDF_PATH = REPO_ROOT / "TA_IBNU_SESUAI_Pedoman_Final.pdf"
assert PDF_PATH.exists(), f"Missing thesis PDF: {PDF_PATH}"

with pdfplumber.open(PDF_PATH) as pdf:
    pdf_pages = [page.extract_text() or "" for page in pdf.pages]

pdf_text = "\\n".join(pdf_pages)
required_pdf_terms = ["Top-5", "NDCG@5", "CTR", "SUS", "Latency p95", "fairness gap", "ablation"]
missing_terms = [term for term in required_pdf_terms if term.lower() not in pdf_text.lower()]
assert not missing_terms, f"PDF metric context missing expected terms: {missing_terms}"

pdf_targets = [
    {"metric": "Top-5 Accuracy", "target": ">= 85%", "notebook_proxy": "hit_rate_at_5 / top5 hit"},
    {"metric": "NDCG@5", "target": ">= 0.85", "notebook_proxy": "ndcg_at_5"},
    {"metric": "CTR", "target": ">= 25%", "notebook_proxy": "interaction CTR proxy"},
    {"metric": "SUS", "target": ">= 70", "notebook_proxy": "not computed - no survey rows"},
    {"metric": "Latency p95", "target": "< 1000 ms", "notebook_proxy": "measured scoring p95"},
    {"metric": "Fairness gap", "target": "< 8 percentage points", "notebook_proxy": "TPR gap by demographic_group"},
]

snippets = []
for page_no, text in enumerate(pdf_pages, start=1):
    lower = text.lower()
    if any(term.lower() in lower for term in required_pdf_terms):
        compact = " ".join(text.split())
        snippets.append({"page": page_no, "snippet": compact[:420]})

display(pd.DataFrame(pdf_targets))
display(pd.DataFrame(snippets[:8]))
"""
        ),
        _markdown(
            """
## 2. Load and Validate the Permanent Sample Dataset

The validation checks schema, critical nulls, valid event labels, user/job ID
consistency, and whether the sample is usable for training and evaluation.
"""
        ),
        _code(
            """
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR, load_sample_dataset, validate_sample_dataset


dataset = load_sample_dataset(DEFAULT_SAMPLE_DIR)
users_df = pd.DataFrame(dataset["users"])
jobs_df = pd.DataFrame(dataset["jobs"])
interactions_df = pd.DataFrame(dataset["interactions"])
milestones_df = pd.DataFrame(dataset["milestones"])

required_fields = {
    "users": {"user_id", "name", "program_studi", "university", "skills", "target_role", "demographic_group", "profile_text"},
    "jobs": {"job_id", "title", "company", "location", "source_url", "description", "skills", "company_logo", "is_active"},
    "interactions": {"user_id", "job_id", "event", "label", "dwell_seconds", "timestamp"},
    "milestones": {"target_role", "action_id", "title", "required_skills", "reward"},
}
frames = {
    "users": users_df,
    "jobs": jobs_df,
    "interactions": interactions_df,
    "milestones": milestones_df,
}

validation_failures: list[str] = []
schema_rows: list[dict[str, Any]] = []
for name, frame in frames.items():
    missing = sorted(required_fields[name] - set(frame.columns))
    schema_rows.append({
        "dataset": name,
        "rows": len(frame),
        "columns": len(frame.columns),
        "missing_required": ", ".join(missing),
    })
    if missing:
        validation_failures.append(f"{name} missing required columns: {missing}")

critical_fields = {
    "users": ["user_id", "profile_text", "target_role", "demographic_group"],
    "jobs": ["job_id", "title", "company", "source_url", "description", "company_logo"],
    "interactions": ["user_id", "job_id", "event", "label"],
    "milestones": ["target_role", "action_id", "title", "required_skills", "reward"],
}
null_rows = []
for name, fields in critical_fields.items():
    frame = frames[name]
    for field in fields:
        null_count = int(frame[field].isna().sum()) if field in frame else -1
        null_rows.append({"dataset": name, "field": field, "critical_nulls": null_count})
        if null_count:
            validation_failures.append(f"{name}.{field} has {null_count} critical nulls")

known_users = set(users_df["user_id"].astype(str))
known_jobs = set(jobs_df["job_id"].astype(str))
interaction_users = set(interactions_df["user_id"].astype(str))
interaction_jobs = set(interactions_df["job_id"].astype(str))
unknown_users = sorted(interaction_users - known_users)
unknown_jobs = sorted(interaction_jobs - known_jobs)
if unknown_users:
    validation_failures.append(f"interactions reference unknown users: {unknown_users}")
if unknown_jobs:
    validation_failures.append(f"interactions reference unknown jobs: {unknown_jobs}")

valid_events = {"impression", "click", "save", "apply", "view", "skip"}
invalid_events = sorted(set(interactions_df["event"].astype(str).str.lower()) - valid_events)
if invalid_events:
    validation_failures.append(f"invalid interaction events: {invalid_events}")
if not interactions_df["label"].between(0.0, 1.0).all():
    validation_failures.append("interaction labels must be in [0, 1]")

validation_failures.extend(validate_sample_dataset(dataset))
assert not validation_failures, "\\n".join(validation_failures)

display(pd.DataFrame(schema_rows))
display(pd.DataFrame(null_rows))
print("Dataset validation passed.")
"""
        ),
        _markdown(
            """
## 3. Load or Generate Lightweight Model Artifacts

The notebook uses existing artifacts when present. If the local evaluation
artifact bundle is absent, it runs the repository's lightweight sample retrain
flow to produce SBERT, NCF, and DQN smoke artifacts.
"""
        ),
        _code(
            """
from scripts.retrain_models import run_retraining


manifest_path = ARTIFACT_DIR / "retraining_manifest.json"
artifact_paths = {
    "sbert": ARTIFACT_DIR / "sbert" / "sbert_similarity_head.pt",
    "ncf": ARTIFACT_DIR / "ncf" / "online_ncf.json",
    "dqn": ARTIFACT_DIR / "dqn" / "dqn_model.pt",
}

if not manifest_path.exists() or not all(path.exists() for path in artifact_paths.values()):
    retraining_result = run_retraining(DEFAULT_SAMPLE_DIR, ARTIFACT_DIR, steps=2)
    artifact_action = "trained_smoke_artifacts"
else:
    retraining_result = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_action = "loaded_existing_artifacts"

artifact_rows = []
for model_name, path in artifact_paths.items():
    artifact_rows.append({
        "model": model_name,
        "path": str(path.relative_to(REPO_ROOT)),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    })

assert all(row["exists"] for row in artifact_rows), artifact_rows
display(pd.DataFrame(artifact_rows))
print(f"Artifact action: {artifact_action}")
print(f"Retraining/evaluation status: {retraining_result.get('status')}")
"""
        ),
        _markdown(
            """
## 4. Generate SBERT, NCF, DQN, and Hybrid Predictions

The ranking flow is:

1. SBERT semantic score for each user-job pair.
2. NCF score loaded from the sample-trained online NCF artifact.
3. DQN job rerank signal used as an aggregation input.
4. Final aggregation through `run_aggregate_stage`.

DQN is also evaluated separately as a career action recommender in the next
section, because its intended output is a learning path rather than only job
postings.
"""
        ),
        _code(
            """
from services.dqn.main import agent as dqn_agent
from services.ncf.main import OnlineNCF
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.sbert.main import deterministic_embedding, sbert_score
from services.sbert.training.train_sbert import SimilarityHead


def job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("location") or ""),
            str(job.get("description") or ""),
            " ".join(map(str, job.get("skills") or [])),
        ]
    )


sbert_head = SimilarityHead()
sbert_head.load_state_dict(torch.load(artifact_paths["sbert"], map_location="cpu"))
sbert_head.eval()


def calibrated_sbert_score(user_text: str, job: dict[str, Any]) -> float:
    base_score = float(sbert_score(user_text, job_text(job)))
    with torch.inference_mode():
        left = torch.tensor(deterministic_embedding(user_text), dtype=torch.float32).unsqueeze(0)
        right = torch.tensor(deterministic_embedding(job_text(job)), dtype=torch.float32).unsqueeze(0)
        head_score = float(((sbert_head(left, right) + 1.0) / 2.0).item())
    return max(0.0, min(1.0, (0.8 * base_score) + (0.2 * head_score)))


ncf_model = OnlineNCF(model_path=artifact_paths["ncf"], autosave=False, load_existing=True)
assert ncf_model.item_factors, "NCF artifact loaded but has no item factors"

label_lookup = {
    (str(row["user_id"]), str(row["job_id"])): float(row["label"])
    for row in dataset["interactions"]
}
interaction_count_by_user = interactions_df.groupby("user_id").size().to_dict()

relevance_by_user = {}
for user in dataset["users"]:
    user_id = str(user["user_id"])
    relevance_by_user[user_id] = {
        str(row["job_id"]): float(row["label"])
        for row in dataset["interactions"]
        if str(row["user_id"]) == user_id and float(row["label"]) >= 0.7
    }

model_rankings: dict[str, dict[str, list[str]]] = {
    "SBERT only": {},
    "NCF only": {},
    "DQN job rerank signal": {},
    "Hybrid / aggregation": {},
}
latencies_ms: dict[str, list[float]] = {name: [] for name in model_rankings}
score_rows: list[dict[str, Any]] = []
hybrid_summaries: dict[str, Any] = {}


async def build_rankings() -> None:
    for user in dataset["users"]:
        user_id = str(user["user_id"])
        user_jobs: list[dict[str, Any]] = []
        for job in dataset["jobs"]:
            started = time.perf_counter()
            sbert_value = calibrated_sbert_score(str(user["profile_text"]), job)
            latencies_ms["SBERT only"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            ncf_value = float(ncf_model.predict_one(user_id, str(job["job_id"]), profile_text=user.get("profile_text")))
            latencies_ms["NCF only"].append((time.perf_counter() - started) * 1000)

            payload = {
                **job,
                "id": str(job["job_id"]),
                "tags": job.get("skills") or [],
                "sbert_score": sbert_value,
                "ncf_score": ncf_value,
            }
            user_jobs.append(payload)

        model_rankings["SBERT only"][user_id] = [
            str(row["job_id"]) for row in sorted(user_jobs, key=lambda row: row["sbert_score"], reverse=True)
        ]
        model_rankings["NCF only"][user_id] = [
            str(row["job_id"]) for row in sorted(user_jobs, key=lambda row: row["ncf_score"], reverse=True)
        ]

        started = time.perf_counter()
        dqn_ranked = dqn_agent.rank(
            user_id,
            user_jobs,
            {"interaction_count": int(interaction_count_by_user.get(user_id, 0))},
        )
        latencies_ms["DQN job rerank signal"].append((time.perf_counter() - started) * 1000)
        dqn_score_by_job = {str(row["job"]["job_id"]): float(row["q_value"]) for row in dqn_ranked}
        model_rankings["DQN job rerank signal"][user_id] = [str(row["job"]["job_id"]) for row in dqn_ranked]

        for row in user_jobs:
            row["dqn_score"] = dqn_score_by_job[str(row["job_id"])]
            score_rows.append({
                "user_id": user_id,
                "job_id": row["job_id"],
                "sbert_score": row["sbert_score"],
                "ncf_score": row["ncf_score"],
                "dqn_score": row["dqn_score"],
                "label": label_lookup.get((user_id, str(row["job_id"])), 0.0),
            })

        started = time.perf_counter()
        aggregate = await run_aggregate_stage(
            {"interaction_count": int(interaction_count_by_user.get(user_id, 0))},
            user_jobs,
        )
        latencies_ms["Hybrid / aggregation"].append((time.perf_counter() - started) * 1000)
        hybrid_summaries[user_id] = aggregate.summary
        model_rankings["Hybrid / aggregation"][user_id] = [str(row["job_id"]) for row in aggregate.ranked]


await build_rankings()
score_df = pd.DataFrame(score_rows)
display(score_df.head(12))
print("Generated rankings for:", ", ".join(model_rankings.keys()))
"""
        ),
        _markdown(
            """
## 5. Ranking Metrics, Coverage, Diversity, Fairness, and Latency

The report uses reusable metric functions from
`services.evaluation.recommendation_metrics`. K=5 is thesis-aligned; K=10 is
included as a second-page sensitivity check. Because the sample catalog has
nine jobs, Precision@10 uses the available recommendation list length.
"""
        ),
        _code(
            """
from services.evaluation.recommendation_metrics import (
    catalog_coverage,
    ctr_proxy,
    fairness_gap_tpr_at_k,
    intra_list_diversity,
    p95_latency_ms,
    ranking_report,
)


group_by_user = {str(row["user_id"]): str(row["demographic_group"]) for row in dataset["users"]}
catalog_ids = [str(row["job_id"]) for row in dataset["jobs"]]
item_features = {str(row["job_id"]): row.get("skills") or [] for row in dataset["jobs"]}
global_ctr_proxy = ctr_proxy(dataset["interactions"])


def observed_ctr_proxy_at_k(rankings: dict[str, list[str]], k: int) -> float:
    values: list[float] = []
    for user_id, ranked_ids in rankings.items():
        for job_id in ranked_ids[:k]:
            values.append(label_lookup.get((user_id, job_id), 0.0))
    return mean(values) if values else 0.0


metrics_rows: list[dict[str, Any]] = []
for model_name, rankings in model_rankings.items():
    row = {"model": model_name}
    row.update(ranking_report(rankings, relevance_by_user, k_values=K_VALUES))
    row["observed_ctr_proxy_at_5"] = observed_ctr_proxy_at_k(rankings, 5)
    row["catalog_coverage_at_5"] = catalog_coverage(rankings, catalog_ids, 5)
    row["intra_list_diversity_at_5"] = intra_list_diversity(rankings, item_features, 5)
    row["latency_p95_ms"] = p95_latency_ms(latencies_ms[model_name])
    fairness = fairness_gap_tpr_at_k(rankings, relevance_by_user, group_by_user, 5)
    row["fairness_gap_pp_at_5"] = fairness["fairness_gap_pp"]
    row["group_tpr_at_5"] = fairness["group_tpr"]
    metrics_rows.append(row)

metrics_df = pd.DataFrame(metrics_rows).sort_values(["ndcg_at_5", "map_at_5"], ascending=False)
rounded_metrics_df = metrics_df.copy()
for column in rounded_metrics_df.columns:
    if column != "model" and column != "group_tpr_at_5":
        rounded_metrics_df[column] = rounded_metrics_df[column].map(lambda value: round(float(value), 6))

display(rounded_metrics_df)
print(f"Global interaction CTR proxy: {global_ctr_proxy:.6f}")
"""
        ),
        _markdown(
            """
## 6. DQN Career Milestone / Action Evaluation

DQN is not evaluated as a random job-posting recommender here. Its intended
output is a next career action or milestone. The metric target is therefore:
given a user's current skills and target role, does `/learning-path` recommend
skills/actions that overlap with the sample milestone requirements?
"""
        ),
        _code(
            """
from services.dqn.main import LearningPathRequest, learning_path


ACTION_VOCAB = [
    "public speaking",
    "english",
    "event",
    "communication",
    "machine learning",
    "dashboard",
    "sql",
    "fastapi",
    "redis",
    "docker",
    "business analysis",
    "presentation",
    "figma",
    "ux research",
    "prototyping",
    "ui design",
]


def extract_action_terms(text: str) -> set[str]:
    lower = text.lower()
    return {term for term in ACTION_VOCAB if term in lower}


def relevant_action_terms(user: dict[str, Any]) -> set[str]:
    mastered = {str(skill).lower() for skill in user.get("skills") or []}
    relevant: set[str] = set()
    for milestone in dataset["milestones"]:
        if str(milestone["target_role"]).lower() != str(user["target_role"]).lower():
            continue
        relevant.update({str(skill).lower() for skill in milestone.get("required_skills") or []} - mastered)
        relevant.update(extract_action_terms(str(milestone.get("title") or "")) - mastered)
    return relevant or {"portfolio"}


dqn_action_rankings: dict[str, list[str]] = {}
dqn_action_relevance: dict[str, set[str]] = {}
dqn_action_rows: list[dict[str, Any]] = []

for user in dataset["users"]:
    response = await learning_path(
        LearningPathRequest(
            user_id=str(user["user_id"]),
            current_skills=list(user.get("skills") or []),
            target_role=str(user.get("target_role") or ""),
        )
    )
    ranked_actions = [str(step.get("skill") or "").lower() for step in response["learning_path"]]
    relevant_actions = relevant_action_terms(user)
    dqn_action_rankings[str(user["user_id"])] = ranked_actions
    dqn_action_relevance[str(user["user_id"])] = relevant_actions
    dqn_action_rows.append({
        "user_id": user["user_id"],
        "target_role": user["target_role"],
        "recommended_actions": ", ".join(ranked_actions),
        "relevant_actions": ", ".join(sorted(relevant_actions)),
    })

dqn_action_metrics = ranking_report(dqn_action_rankings, dqn_action_relevance, k_values=(3, 5))
display(pd.DataFrame(dqn_action_rows))
display(pd.DataFrame([{"metric": key, "value": round(value, 6)} for key, value in dqn_action_metrics.items()]))
"""
        ),
        _markdown(
            """
## 7. Hybrid Comparison and Visualizations

The tables and charts compare SBERT-only, NCF-only, DQN job rerank signal, and
the final hybrid aggregation. The DQN action table above is kept separate
because its primary output is a learning path.
"""
        ),
        _code(
            """
ranking_chart_path = REPORTS_DIR / "evaluation_metrics_ranking_bars.png"
latency_chart_path = REPORTS_DIR / "evaluation_metrics_latency_fairness.png"

comparison_columns = ["model", "precision_at_5", "recall_at_5", "ndcg_at_5", "hit_rate_at_5", "map_at_5", "mrr_at_5"]
comparison_df = rounded_metrics_df[comparison_columns].copy()
display(comparison_df)

plot_df = metrics_df.set_index("model")[["precision_at_5", "recall_at_5", "ndcg_at_5"]]
ax = plot_df.plot(kind="bar", figsize=(10, 5), ylim=(0, 1.05), rot=20)
ax.set_title("SCPA Ranking Metrics at K=5")
ax.set_ylabel("score")
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(ranking_chart_path, dpi=160)
plt.show()

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
metrics_df.plot(x="model", y="latency_p95_ms", kind="bar", ax=axes[0], legend=False, rot=20)
axes[0].axhline(1000, linestyle="--", color="red", linewidth=1)
axes[0].set_title("Latency p95 by model")
axes[0].set_ylabel("milliseconds")
metrics_df.plot(x="model", y="fairness_gap_pp_at_5", kind="bar", ax=axes[1], legend=False, rot=20)
axes[1].axhline(8, linestyle="--", color="red", linewidth=1)
axes[1].set_title("Fairness gap at K=5")
axes[1].set_ylabel("percentage points")
for axis in axes:
    axis.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(latency_chart_path, dpi=160)
plt.show()

print(f"Saved charts: {ranking_chart_path.name}, {latency_chart_path.name}")
"""
        ),
        _markdown(
            """
## 8. E2E Metric Smoke Test and Exportable Result

This final section proves the flow completed:

sample users/jobs/interactions -> model prediction/ranking -> metrics
calculation -> final comparison report.
"""
        ),
        _code(
            """
def to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_builtin(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


report_csv = REPORTS_DIR / "evaluation_metrics_report.csv"
summary_json = REPORTS_DIR / "evaluation_metrics_summary.json"

rounded_metrics_df.to_csv(report_csv, index=False)
hybrid_row = metrics_df.loc[metrics_df["model"] == "Hybrid / aggregation"].iloc[0]

target_checks = {
    "hybrid_hit_rate_at_5_target_0.85": bool(float(hybrid_row["hit_rate_at_5"]) >= 0.85),
    "hybrid_ndcg_at_5_target_0.85": bool(float(hybrid_row["ndcg_at_5"]) >= 0.85),
    "interaction_ctr_proxy_target_0.25": bool(float(global_ctr_proxy) >= 0.25),
    "hybrid_latency_p95_under_1000ms": bool(float(hybrid_row["latency_p95_ms"]) < 1000.0),
    "hybrid_fairness_gap_under_8pp": bool(float(hybrid_row["fairness_gap_pp_at_5"]) < 8.0),
    "dqn_action_hit_rate_at_3_target_0.80": bool(float(dqn_action_metrics["hit_rate_at_3"]) >= 0.80),
}

summary = {
    "pdf": {
        "path": str(PDF_PATH.relative_to(REPO_ROOT)),
        "pages": len(pdf_pages),
        "targets": pdf_targets,
    },
    "dataset": {
        "sample_dir": str(DEFAULT_SAMPLE_DIR.relative_to(REPO_ROOT)),
        "counts": {name: int(len(frame)) for name, frame in frames.items()},
        "valid_events": sorted(valid_events),
        "validation_failures": validation_failures,
    },
    "artifacts": {
        "action": artifact_action,
        "manifest": str(manifest_path.relative_to(REPO_ROOT)),
        "models": artifact_rows,
    },
    "global_ctr_proxy": float(global_ctr_proxy),
    "ranking_metrics": rounded_metrics_df.to_dict(orient="records"),
    "dqn_action_metrics": {key: float(value) for key, value in dqn_action_metrics.items()},
    "target_checks": target_checks,
    "reports": {
        "csv": str(report_csv.relative_to(REPO_ROOT)),
        "summary_json": str(summary_json.relative_to(REPO_ROOT)),
        "ranking_chart": str(ranking_chart_path.relative_to(REPO_ROOT)),
        "latency_chart": str(latency_chart_path.relative_to(REPO_ROOT)),
    },
}
summary_json.write_text(json.dumps(to_builtin(summary), indent=2) + "\\n", encoding="utf-8")

assert report_csv.exists(), report_csv
assert summary_json.exists(), summary_json
assert ranking_chart_path.exists(), ranking_chart_path
assert latency_chart_path.exists(), latency_chart_path
assert all(target_checks.values()), target_checks

print("E2E metrics validation passed.")
print(json.dumps(target_checks, indent=2))
print(f"Wrote {report_csv}")
print(f"Wrote {summary_json}")
"""
        ),
    ]
    return nb


def write_notebook(path: Path = NOTEBOOK_PATH) -> None:
    nb = build_notebook()
    nbformat.validate(nb)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)


def main() -> int:
    write_notebook()
    print(NOTEBOOK_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
