"""Build the executable SCPA ML readiness evaluation notebook."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "scpa_ml_readiness_evaluation.ipynb"


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
# SCPA Backend ML Readiness Evaluation

## Abstract

This notebook is the executable evidence bundle for the SCPA recommendation
backend. It combines deterministic service fixtures, ranking and operational
metrics, literature-aligned interpretation, and an automated pass/fail gate for
the current ML readiness target.

The evaluation is intentionally framed like a small empirical paper: it states
the research questions, cites the metric assumptions, defines the service
pipeline under test, exposes the data used for each service, renders the
requested figures, and ends with reproducible assertions. The outputs are
written to `notebooks/training_runs/readiness/`; service fixtures are written to
`services/*/training/data/`.

Primary evidence areas:

- ranking quality: Top-5, NDCG@5, HR@10
- behavioral quality: CTR, SUS
- operational quality: P95 latency, cache hit rate, fairness gap
- policy quality: DQN reward lift versus random ordering
- hybrid tuning: alpha sweep against NDCG@5
- pipeline quality: deduplication and verification mismatch checks
"""
        ),
        _markdown(
            """
## 1. Literature and Web Evidence

This notebook uses five source groups:

1. Petersen et al., *Differentiable Top-k Classification Learning*, for the
   claim that top-k accuracy is a core metric and that evaluating only a single
   rank can miss useful ranking behavior.
2. Jeunen et al., *On (Normalised) Discounted Cumulative Gain as an Offline
   Evaluation Metric for Top-n Recommendation*, for the offline-online caveat:
   NDCG is useful, but its assumptions, normalization, and sampling choices
   must be made explicit.
3. Li et al., *CTRL: Connect Collaborative and Language Model for CTR
   Prediction*, for the recommender pattern that combines collaborative signals
   with semantic signals while keeping online serving efficient.
4. Hyzy et al., *System Usability Scale Benchmarking for Digital Health Apps*,
   for the SUS benchmark context around the conventional 68 mean and a stricter
   readiness threshold.
5. DSWOK's recommendation-system page, scraped in Chrome from
   `https://dswok.com/Use_cases/Recommendation-system`, for production system
   design: retrieval, ranking, re-ranking, time-based evaluation, monitoring,
   latency guardrails, calibration, and training-serving skew.

The notebook does not claim that fixture metrics prove online impact. It
instead asks whether SCPA has a coherent, testable, and production-shaped
offline readiness package that can graduate to a time-split validation set,
shadow serving, and controlled online experiments.
"""
        ),
        _code(
            """
from pathlib import Path
import json
import math
import sys

import pandas as pd
from IPython.display import Image, Markdown, display


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "SCPA_Backend_ML_Plan.md").exists():
            return candidate
    raise RuntimeError("Could not locate SCPA repo root")


REPO_ROOT = find_repo_root(Path.cwd().resolve())
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = REPO_ROOT / "notebooks" / "training_runs" / "readiness"
DATA_ROOT = REPO_ROOT / "services"
NOTEBOOK_DATA_DIR = REPO_ROOT / "notebooks" / "data"

SOURCE_REGISTER = [
    {
        "source_id": "top_k",
        "title": "Differentiable Top-k Classification Learning",
        "local_path": "2206.07290v1.pdf",
        "used_for": "Top-k framing and multi-rank evaluation rationale",
    },
    {
        "source_id": "dcg_ndcg",
        "title": "On (Normalised) Discounted Cumulative Gain as an Offline Evaluation Metric for Top-n Recommendation",
        "local_path": "On_Normalised_Discounted_Cumulative_Gain_as_an_Off.pdf",
        "used_for": "NDCG assumptions, offline-online mismatch, and sampling caveats",
    },
    {
        "source_id": "ctrl_ctr",
        "title": "CTRL: Connect Collaborative and Language Model for CTR Prediction",
        "local_path": "2306.02841v4.pdf",
        "used_for": "Collaborative plus semantic CTR modeling and efficient online serving",
    },
    {
        "source_id": "sus_benchmark",
        "title": "System Usability Scale Benchmarking for Digital Health Apps",
        "local_path": "mhealth_v10i8e37290.pdf",
        "used_for": "SUS benchmark context and reporting discipline",
    },
    {
        "source_id": "dswok_recsys",
        "title": "DSWOK Recommendation system",
        "url": "https://dswok.com/Use_cases/Recommendation-system",
        "used_for": "Production recommender pipeline, evaluation, monitoring, and failure modes",
    },
]

for source in SOURCE_REGISTER:
    local_path = source.get("local_path")
    if local_path:
        assert (REPO_ROOT / local_path).exists(), f"Missing source PDF: {local_path}"

display(pd.DataFrame(SOURCE_REGISTER))
print(f"Repo root: {REPO_ROOT}")
print(f"Output dir: {OUTPUT_DIR}")
print(f"Data root: {DATA_ROOT}")
"""
        ),
        _markdown(
            """
## 2. Research Questions and Evaluation Contract

The readiness evaluation answers four questions:

1. Can the backend produce non-empty training or evaluation fixtures for every
   ML service boundary: Pipeline, SBERT, NCF, DQN, and Hybrid?
2. Do the offline ranking and behavioral metrics pass the thesis readiness
   targets?
3. Do operational guardrails make the ranking result deployable, not just
   accurate in a notebook?
4. Are the remaining limitations explicit enough for a thesis reader or
   reviewer to reproduce and challenge the result?

Metric definitions used in this notebook:

$$DCG@k = \\sum_{i=1}^{k} \\frac{rel_i}{\\log_2(i + 1)}$$

$$NDCG@k = \\frac{DCG@k}{IDCG@k}$$

$$HR@k = \\frac{1}{|U|}\\sum_u I(\\text{relevant item appears in top } k)$$

$$RewardLift = \\frac{mean(DQN\\ reward)}{mean(random\\ reward)}$$
"""
        ),
        _code(
            """
EVALUATION_CONTRACT = [
    {
        "metric": "top5_accuracy",
        "target": ">= 0.85",
        "source_alignment": "top_k",
        "interpretation": "The correct job should appear in the first five recommendations.",
    },
    {
        "metric": "ndcg_at_5",
        "target": ">= 0.85",
        "source_alignment": "dcg_ndcg",
        "interpretation": "Relevant jobs should appear early, with assumptions documented.",
    },
    {
        "metric": "hit_rate_at_10",
        "target": ">= 0.45",
        "source_alignment": "dswok_recsys",
        "interpretation": "Retrieval and ranking should retain a relevant item in the first page.",
    },
    {
        "metric": "ctr",
        "target": ">= 0.25",
        "source_alignment": "ctrl_ctr",
        "interpretation": "The recommender should preserve a meaningful click-through proxy.",
    },
    {
        "metric": "sus",
        "target": ">= 70",
        "source_alignment": "sus_benchmark",
        "interpretation": "The UX proxy should clear the conventional SUS mean benchmark.",
    },
    {
        "metric": "p95_latency_ms",
        "target": "<= 1000",
        "source_alignment": "dswok_recsys",
        "interpretation": "The full recommendation path should remain within an interactive budget.",
    },
    {
        "metric": "cache_hit_rate",
        "target": ">= 0.60",
        "source_alignment": "dswok_recsys",
        "interpretation": "Cached candidates should absorb enough repeated serving traffic.",
    },
    {
        "metric": "fairness_gap_pp",
        "target": "<= 8",
        "source_alignment": "dswok_recsys",
        "interpretation": "Group-level recommendation quality should stay within the fairness guardrail.",
    },
    {
        "metric": "dqn_reward_lift",
        "target": ">= 1.5",
        "source_alignment": "dswok_recsys",
        "interpretation": "The learned policy should beat random ordering by a practical margin.",
    },
]

display(pd.DataFrame(EVALUATION_CONTRACT))
"""
        ),
        _markdown(
            """
## 3. Generate Service Fixtures and Readiness Artifacts

This cell creates deterministic, inspectable data for Pipeline, SBERT, NCF,
DQN, and Hybrid. It then computes readiness metrics and renders PNG and HTML
report assets.

The fixtures are deliberately small because they are contract tests for the ML
surface, not final model training data. Production evaluation should reuse the
same metric contract on a time-based split with logged impressions and
propensities.
"""
        ),
        _code(
            """
from scripts.generate_ml_readiness_assets import TARGETS, generate_all

result = generate_all(output_dir=OUTPUT_DIR, data_root=DATA_ROOT)
metrics = result["metrics"]

summary = {
    "ready": metrics["ready"],
    "metrics_path": str(result["metrics_path"].relative_to(REPO_ROOT)),
    "csv_path": str(result["csv_path"].relative_to(REPO_ROOT)),
    "report_path": str(result["report_path"].relative_to(REPO_ROOT)),
    "figure_count": len(result["figures"]),
    "service_data_count": len(result["data"]),
}
summary
"""
        ),
        _markdown(
            """
## 4. Data Manifest and Schema Audit

Each service fixture is inspected for file size, record count, and schema keys.
The goal is to make the evidence auditable from inside the notebook and to
catch empty or malformed training surfaces before model work begins.
"""
        ),
        _code(
            """
def read_jsonl_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_records(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return read_jsonl_rows(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return [payload]


manifest_rows = []
for service, path in sorted(result["data"].items()):
    path = Path(path)
    records = load_records(path)
    keys = sorted({key for row in records if isinstance(row, dict) for key in row})
    manifest_rows.append(
        {
            "service": service,
            "path": str(path.relative_to(REPO_ROOT)),
            "records": len(records),
            "bytes": path.stat().st_size,
            "schema_keys": ", ".join(keys),
        }
    )

manifest_df = pd.DataFrame(manifest_rows)
display(manifest_df)
assert (manifest_df["records"] > 0).all()
assert (manifest_df["bytes"] > 0).all()
"""
        ),
        _markdown(
            """
## 5. Existing Notebook Data Assets

The generated readiness fixtures are the contract layer. The repository also
contains larger local notebook data under `notebooks/data/`. This audit keeps
those assets visible so the next phase can move from deterministic fixtures to
larger time-split validation.
"""
        ),
        _code(
            """
local_data_rows = []
candidate_files = [
    NOTEBOOK_DATA_DIR / "scpa_jobs_training.jsonl",
    NOTEBOOK_DATA_DIR / "hybrid_validation_sessions.json",
]

for path in candidate_files:
    if not path.exists():
        local_data_rows.append(
            {
                "asset": str(path.relative_to(REPO_ROOT)),
                "exists": False,
                "records": 0,
                "bytes": 0,
                "schema_keys": "",
            }
        )
        continue
    records = load_records(path)
    keys = sorted({key for row in records if isinstance(row, dict) for key in row})
    local_data_rows.append(
        {
            "asset": str(path.relative_to(REPO_ROOT)),
            "exists": True,
            "records": len(records),
            "bytes": path.stat().st_size,
            "schema_keys": ", ".join(keys),
        }
    )

local_data_df = pd.DataFrame(local_data_rows)
display(local_data_df)
"""
        ),
        _markdown(
            """
## 6. Service Role Map

The SCPA service split maps cleanly onto the production recommender pattern from
the scraped DSWOK page: ingestion and deduplication, semantic retrieval,
collaborative ranking, policy optimization, and hybrid re-ranking. The CTRL
paper motivates the same separation between collaborative and semantic signals,
with a lightweight online serving path.
"""
        ),
        _code(
            """
SERVICE_ROLE_MAP = [
    {
        "service": "pipeline",
        "recsys_stage": "data preparation",
        "readiness_evidence": "deduplication, normalization, verification",
        "failure_mode_checked": "duplicate jobs and verification mismatches",
    },
    {
        "service": "sbert",
        "recsys_stage": "semantic retrieval",
        "readiness_evidence": "query-positive-negative training pairs",
        "failure_mode_checked": "empty semantic supervision surface",
    },
    {
        "service": "ncf",
        "recsys_stage": "collaborative ranking",
        "readiness_evidence": "implicit feedback interactions",
        "failure_mode_checked": "missing click/save/apply labels",
    },
    {
        "service": "dqn",
        "recsys_stage": "policy optimization",
        "readiness_evidence": "episode rewards versus random ordering",
        "failure_mode_checked": "policy weaker than random baseline",
    },
    {
        "service": "hybrid",
        "recsys_stage": "score fusion and re-ranking",
        "readiness_evidence": "NCF, SBERT, and DQN score blending",
        "failure_mode_checked": "uniform alpha beats tuned alpha",
    },
]

display(pd.DataFrame(SERVICE_ROLE_MAP))
"""
        ),
        _markdown(
            """
## 7. Readiness Matrix

The table below reports the exact metric values, target direction, margin, and
pass status. This mirrors the machine-readable JSON and CSV artifacts written
by the generator.
"""
        ),
        _code(
            """
readiness_df = pd.DataFrame(metrics["readiness"]).copy()
readiness_df["target_rule"] = readiness_df.apply(
    lambda row: f">= {row['target']:g}" if row["direction"] == "min" else f"<= {row['target']:g}",
    axis=1,
)
readiness_df["margin"] = readiness_df.apply(
    lambda row: row["value"] - row["target"]
    if row["direction"] == "min"
    else row["target"] - row["value"],
    axis=1,
)
readiness_df["status"] = readiness_df["passed"].map({True: "PASS", False: "CHECK"})

display(
    readiness_df[
        ["metric", "label", "value", "target_rule", "margin", "status"]
    ].sort_values("metric")
)

failed = readiness_df.loc[~readiness_df["passed"]]
assert failed.empty, failed.to_dict(orient="records")
assert metrics["ready"] is True
"""
        ),
        _markdown(
            """
## 8. Metric Interpretation

The values pass the configured readiness targets, but they should be read with
the correct scope:

- Top-k and HR@k validate that relevant jobs survive ranking.
- NDCG@5 rewards early placement, but the DCG/NDCG paper warns that offline
  ranking metrics can diverge from online reward if logging and candidate
  assumptions are wrong.
- CTR is a product proxy, not the whole product goal. The DSWOK notes warn that
  CTR can rise while satisfaction or long-term retention falls.
- SUS is benchmarked against a conventional mean around 68; this notebook uses
  a stricter 70 target to avoid passing on a merely average usability proxy.
- P95 latency and cache hit rate keep the system deployable under interactive
  serving constraints.
"""
        ),
        _code(
            """
metric_interpretation = []
for row in readiness_df.to_dict(orient="records"):
    contract = next(item for item in EVALUATION_CONTRACT if item["metric"] == row["metric"])
    metric_interpretation.append(
        {
            "metric": row["metric"],
            "value": row["value"],
            "target": row["target_rule"],
            "status": row["status"],
            "source_alignment": contract["source_alignment"],
            "interpretation": contract["interpretation"],
        }
    )

display(pd.DataFrame(metric_interpretation))
"""
        ),
        _markdown(
            """
## 9. Requested Evaluation Graphics

The generated figures cover all requested thesis plots:

- readiness matrix: Top-5, NDCG@5, HR@10, CTR, SUS, P95, cache hit, fairness
- operational matrix: latency, cache, fairness, service quality
- DQN reward versus random baseline
- hybrid alpha tuning
- pipeline deduplication and verification
"""
        ),
        _code(
            """
figure_order = [
    ("readiness_matrix", "Readiness matrix: NDCG, HR, CTR, SUS, P95, cache hit, fairness"),
    ("operational_matrix", "Operational matrix: latency, cache, fairness, service quality"),
    ("dqn_reward_vs_random", "DQN reward vs random baseline"),
    ("alpha_tuning", "Hybrid alpha tuning"),
    ("pipeline_quality", "Pipeline dedup and verification"),
]

for key, title in figure_order:
    path = Path(result["figures"][key])
    display(Markdown(f"### {title}\\n`{path.relative_to(REPO_ROOT)}`"))
    display(Image(filename=str(path)))
"""
        ),
        _markdown(
            """
## 10. Service Fixture Preview

Small previews make the generated fixtures inspectable without opening each
JSON or JSONL file separately.
"""
        ),
        _code(
            """
def preview_records(path: Path, limit: int = 3) -> list[dict]:
    return load_records(path)[:limit]


for service, path in sorted(result["data"].items()):
    path = Path(path)
    display(Markdown(f"### {service}: `{path.relative_to(REPO_ROOT)}`"))
    display(pd.DataFrame(preview_records(path)))
"""
        ),
        _markdown(
            """
## 11. Operational Guardrails

This guardrail table translates the web-scraped DSWOK production checklist into
checks SCPA can run or plan next. Some are proven by the current readiness
fixtures; others are explicit next gates for shadow serving or live experiments.
"""
        ),
        _code(
            """
OPERATIONAL_GUARDRAILS = [
    {
        "guardrail": "P95 latency",
        "current_evidence": metrics["metrics"]["p95_latency_ms"],
        "target": "<= 1000 ms",
        "status": "PASS" if metrics["metrics"]["p95_latency_ms"] <= TARGETS["p95_latency_ms"]["target"] else "CHECK",
        "next_gate": "Measure P99 and per-service latency in a live compose stack.",
    },
    {
        "guardrail": "cache hit rate",
        "current_evidence": metrics["metrics"]["cache_hit_rate"],
        "target": ">= 0.60",
        "status": "PASS" if metrics["metrics"]["cache_hit_rate"] >= TARGETS["cache_hit_rate"]["target"] else "CHECK",
        "next_gate": "Break down hit rate by head users, tail users, and cold-start users.",
    },
    {
        "guardrail": "fairness gap",
        "current_evidence": metrics["metrics"]["fairness_gap_pp"],
        "target": "<= 8 pp",
        "status": "PASS" if metrics["metrics"]["fairness_gap_pp"] <= TARGETS["fairness_gap_pp"]["target"] else "CHECK",
        "next_gate": "Slice by program, geography, tenure, and device after real impressions exist.",
    },
    {
        "guardrail": "training-serving skew",
        "current_evidence": "fixture schema audited",
        "target": "logged feature parity",
        "status": "PLANNED",
        "next_gate": "Shadow-log served features and diff them against offline feature generation.",
    },
    {
        "guardrail": "counterfactual bias",
        "current_evidence": "offline assumptions documented",
        "target": "propensity-aware logs",
        "status": "PLANNED",
        "next_gate": "Log displayed item, position, candidate source, score, and propensity.",
    },
    {
        "guardrail": "calibration drift",
        "current_evidence": "CTR proxy tracked",
        "target": "per-segment calibration",
        "status": "PLANNED",
        "next_gate": "Add ECE or calibration curves once impression labels are available.",
    },
]

display(pd.DataFrame(OPERATIONAL_GUARDRAILS))
"""
        ),
        _markdown(
            """
## 12. Alpha Tuning and Policy Lift

The hybrid layer must not merely blend models arbitrarily. It should show that
tuned score fusion beats a uniform blend, while DQN policy reward beats random
ordering by a practical margin.
"""
        ),
        _code(
            """
alpha_df = pd.DataFrame(metrics["alpha_tuning"]["curve"])
best_alpha = metrics["alpha_tuning"]["best_alpha"]
uniform_ndcg = metrics["alpha_tuning"]["uniform_alpha_ndcg_at_5"]
best_ndcg = metrics["alpha_tuning"]["best_ndcg_at_5"]

display(alpha_df)
print(f"Best alpha: {best_alpha}")
print(f"Best NDCG@5: {best_ndcg}")
print(f"Uniform alpha NDCG@5: {uniform_ndcg}")
print(f"DQN reward lift: {metrics['metrics']['dqn_reward_lift']}")

assert best_ndcg > uniform_ndcg
assert metrics["metrics"]["dqn_reward_lift"] >= TARGETS["dqn_reward_lift"]["target"]
"""
        ),
        _markdown(
            """
## 13. Metric Details

This cell exposes the exact JSON payload used by the graphics, report, and
tests. It is intentionally redundant with the tables above so readers can
verify the machine-readable artifact directly.
"""
        ),
        _code(
            """
metric_values = pd.DataFrame(
    [{"metric": key, "value": value} for key, value in metrics["metrics"].items()]
)
display(metric_values)

print(
    json.dumps(
        {
            "pipeline": metrics["pipeline"],
            "alpha_tuning": metrics["alpha_tuning"],
            "ready": metrics["ready"],
        },
        indent=2,
    )
)
"""
        ),
        _markdown(
            """
## 14. Threats to Validity

The current notebook is strong as an executable readiness bundle, but it has
known limits:

- The generated fixtures are deterministic and small; they prove service
  contracts, not production generalization.
- NDCG@5 is computed on fully known fixture candidates. Production use must
  avoid sampled metric shortcuts unless the sampling assumptions are explicit.
- CTR and SUS are proxy measurements. They need real user interaction, surveys,
  or controlled experiments before being claimed as product impact.
- The fairness gap is a readiness guardrail, not a full fairness audit.
- The DQN reward comparison is an offline policy test; it should be followed by
  shadow serving before online rollout.

Recommended next gates: time-based validation split, impression logging with
positions and propensities, calibration plots, per-segment metrics, P99 latency,
and a champion-versus-candidate report.
"""
        ),
        _markdown(
            """
## 15. Final Notebook Gate

This final gate mirrors the test suite expectations: zero pipeline duplicates,
zero verification mismatches, tuned alpha beating uniform alpha, and DQN lift
of at least 1.5x random ordering.
"""
        ),
        _code(
            """
assert metrics["pipeline"]["duplicate_job_ids_after_dedup"] == 0
assert metrics["pipeline"]["verification_mismatches"] == 0
assert metrics["alpha_tuning"]["best_ndcg_at_5"] > metrics["alpha_tuning"]["uniform_alpha_ndcg_at_5"]
assert metrics["metrics"]["dqn_reward_lift"] >= TARGETS["dqn_reward_lift"]["target"]
assert metrics["ready"] is True

print("SCPA ML readiness notebook completed successfully.")
"""
        ),
        _markdown(
            """
## References

- Petersen, F., Kuehne, H., Borgelt, C., and Deussen, O. *Differentiable
  Top-k Classification Learning*. Local PDF: `2206.07290v1.pdf`.
- Jeunen, O., Potapov, I., and Ustimenko, A. *On (Normalised) Discounted
  Cumulative Gain as an Offline Evaluation Metric for Top-n Recommendation*.
  Local PDF: `On_Normalised_Discounted_Cumulative_Gain_as_an_Off.pdf`.
- Li, X., Chen, B., Hou, L., and Tang, R. *CTRL: Connect Collaborative and
  Language Model for CTR Prediction*. Local PDF: `2306.02841v4.pdf`.
- Hyzy, M., Bond, R., Mulvenna, M., Bai, L., Dix, A., Leigh, S., and Hunt, S.
  *System Usability Scale Benchmarking for Digital Health Apps*. Local PDF:
  `mhealth_v10i8e37290.pdf`.
- DSWOK. *Recommendation system*.
  `https://dswok.com/Use_cases/Recommendation-system`.
"""
        ),
    ]
    return nb


def write_notebook(path: Path = NOTEBOOK_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    nb = build_notebook()
    nbformat.validate(nb)
    nbformat.write(nb, path)
    return path


def main() -> int:
    path = write_notebook()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
