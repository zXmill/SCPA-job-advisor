"""Build SBERT relevance qrels (silver + gold) with an auditable adjudication.

The SBERT retrieval evaluation already runs on the real fine-tuned model, but
its ground truth is *silver* (heuristic ``system_relevance_grade``). To claim
expert Precision/NDCG the thesis needs **gold** qrels: independent human grades
adjudicated into a single relevance label, with inter-annotator agreement
reported.

This script:
  1. Emits silver qrels from the heuristic system grade (always available).
  2. Adjudicates annotator grades into gold qrels when present, using a
     documented rule, and computes linear-weighted Cohen's kappa.
  3. Emits an annotation-ready template for the rows still missing grades.
  4. Writes an honest status report (BLOCKED until expert grades exist).

Pure-stdlib CSV only (no pandas) to avoid the known Windows pyarrow crash.

Run:
  python -m scripts.eval.build_gold_qrels
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

GRADE_MIN, GRADE_MAX = 0, 3


def _maybe_int(value: Any) -> int | None:
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def load_annotation(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def linear_weighted_cohen_kappa(pairs: list[tuple[int, int]]) -> dict[str, Any]:
    """Linear-weighted Cohen's kappa for ordinal grades 0..GRADE_MAX.

    Returns kappa and the observed/expected disagreement so the value is
    transparent. Requires both annotators present on each pair.
    """
    n = len(pairs)
    if n == 0:
        return {"kappa": None, "n": 0, "note": "no double-annotated pairs"}

    categories = list(range(GRADE_MIN, GRADE_MAX + 1))
    max_dist = GRADE_MAX - GRADE_MIN

    def weight(a: int, b: int) -> float:
        # 1.0 = full agreement, 0.0 = maximal disagreement (linear).
        return 1.0 - abs(a - b) / max_dist if max_dist else 1.0

    marg_a = Counter(a for a, _ in pairs)
    marg_b = Counter(b for _, b in pairs)

    observed = sum(weight(a, b) for a, b in pairs) / n
    expected = sum(
        weight(ca, cb) * (marg_a.get(ca, 0) / n) * (marg_b.get(cb, 0) / n)
        for ca in categories
        for cb in categories
    )
    kappa = (observed - expected) / (1.0 - expected) if (1.0 - expected) else 1.0
    return {
        "kappa": round(kappa, 4),
        "n": n,
        "observed_agreement": round(observed, 4),
        "expected_agreement": round(expected, 4),
        "interpretation": _kappa_label(kappa),
        "weighting": "linear",
    }


def _kappa_label(kappa: float) -> str:
    if kappa < 0.0:
        return "poor (worse than chance)"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


def adjudicate(grade_a: int | None, grade_b: int | None, existing: int | None) -> tuple[int | None, str]:
    """Documented adjudication rule -> (gold_grade, decision)."""
    if existing is not None:
        return existing, "preset_adjudicated"
    if grade_a is None and grade_b is None:
        return None, "pending_no_grades"
    if grade_a is None or grade_b is None:
        present = grade_a if grade_a is not None else grade_b
        return present, "single_annotator_only"
    if grade_a == grade_b:
        return grade_a, "consensus"
    if abs(grade_a - grade_b) == 1:
        # Adjacent disagreement: take the lower (conservative relevance).
        return min(grade_a, grade_b), "adjacent_resolved_conservative"
    return None, "needs_third_adjudicator"


def build(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_annotation(args.annotation)
    args.qrels_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    silver_path = args.qrels_dir / "silver_qrels.csv"
    gold_path = args.qrels_dir / "gold_qrels.csv"
    template_path = args.qrels_dir / "annotation_template.csv"

    silver_rows: list[list[Any]] = []
    gold_rows: list[list[Any]] = []
    template_rows: list[dict[str, Any]] = []
    kappa_pairs: list[tuple[int, int]] = []
    decisions: Counter[str] = Counter()

    for row in rows:
        qid = row.get("query_id") or row.get("profile_id")
        cid = row.get("job_id")
        if not qid or not cid:
            continue
        system_grade = _maybe_int(row.get("system_relevance_grade"))
        if system_grade is not None:
            silver_rows.append([qid, cid, system_grade, "silver_heuristic", row.get("labeling_reason", "")])

        a = _maybe_int(row.get("annotator_1_grade"))
        b = _maybe_int(row.get("annotator_2_grade"))
        existing = _maybe_int(row.get("adjudicated_grade"))
        if a is not None and b is not None:
            kappa_pairs.append((max(GRADE_MIN, min(GRADE_MAX, a)), max(GRADE_MIN, min(GRADE_MAX, b))))

        gold, decision = adjudicate(a, b, existing)
        decisions[decision] += 1
        if gold is not None:
            gold_rows.append([qid, cid, gold, "gold_adjudicated", decision])
        else:
            template_rows.append({
                "annotation_id": row.get("annotation_id", ""),
                "query_id": qid,
                "job_id": cid,
                "query_text": (row.get("query_text") or "")[:400],
                "job_title": row.get("job_title", ""),
                "company": row.get("company", ""),
                "system_relevance_grade": system_grade if system_grade is not None else "",
                "annotator_1_grade": "",
                "annotator_2_grade": "",
                "adjudicated_grade": "",
                "guideline": "grade 0=irrelevant, 1=marginal, 2=relevant, 3=highly relevant",
            })

    # Write silver qrels (always available).
    with silver_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["qid", "cid", "relevance", "label_source", "notes"])
        writer.writerows(silver_rows)

    # Write gold qrels (may be empty until expert grades arrive).
    with gold_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["qid", "cid", "relevance", "label_source", "decision"])
        writer.writerows(gold_rows)

    # Write annotation template for the still-ungraded rows.
    if template_rows:
        with template_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(template_rows[0].keys()))
            writer.writeheader()
            writer.writerows(template_rows)

    kappa = linear_weighted_cohen_kappa(kappa_pairs)
    gold_ready = len(gold_rows) > 0 and len(template_rows) == 0
    status = "READY" if gold_ready else "BLOCKED"

    silver_grade_dist = Counter(r[2] for r in silver_rows)
    report = {
        "status": status,
        "annotation_source": str(args.annotation),
        "total_annotation_rows": len(rows),
        "silver_qrels": {
            "path": str(silver_path),
            "n_judgements": len(silver_rows),
            "grade_distribution": {str(k): v for k, v in sorted(silver_grade_dist.items())},
            "label_source": "system_relevance_grade (heuristic, NOT expert)",
        },
        "gold_qrels": {
            "path": str(gold_path),
            "n_judgements": len(gold_rows),
            "adjudication_decisions": dict(decisions),
            "inter_annotator_agreement": kappa,
        },
        "annotation_template": {
            "path": str(template_path) if template_rows else None,
            "n_rows_pending_expert_grade": len(template_rows),
        },
        "claim_boundary": {
            "can_claim_now": [
                "Silver Precision@K / NDCG@K on the real fine-tuned SBERT (heuristic ground truth).",
                "A full adjudication pipeline and annotation protocol exist and are reproducible.",
            ],
            "cannot_claim_until_gold": [
                "Expert-validated Precision@K / NDCG@K.",
                "Inter-annotator agreement (kappa) as evidence of label quality.",
            ],
            "next_step": (
                "Two annotators grade annotation_template.csv (0-3); re-run this "
                "script to adjudicate into gold_qrels.csv and report Cohen's kappa."
            ),
        },
    }

    (args.report_dir / "gold_qrels_status.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [
        "# SBERT Gold Qrels Status\n",
        f"Status: `{status}`\n",
        f"- Annotation rows: {len(rows)}",
        f"- Silver judgements: {len(silver_rows)} (`{silver_path.name}`) — heuristic, not expert",
        f"- Gold judgements: {len(gold_rows)} (`{gold_path.name}`)",
        f"- Pending expert grade: {len(template_rows)} (`annotation_template.csv`)",
        f"- Inter-annotator agreement (linear-weighted Cohen's kappa): "
        f"`{kappa.get('kappa')}` ({kappa.get('interpretation', 'n/a')}, n={kappa.get('n')})\n",
        "## Adjudication decisions\n",
        *[f"- {decision}: {count}" for decision, count in decisions.items()],
        "\n## What can be claimed now\n",
        "- Silver Precision@K / NDCG@K on the real fine-tuned SBERT.",
        "- A reproducible adjudication + agreement pipeline (this script).\n",
        "## What needs expert grades\n",
        "- Expert-validated Precision@K / NDCG@K and a reported kappa.",
        "- Next: two annotators fill `annotation_template.csv` (0-3), then re-run this script.\n",
    ]
    (args.report_dir / "gold_qrels_status.md").write_text("\n".join(md), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SBERT silver/gold qrels with adjudication")
    parser.add_argument(
        "--annotation",
        type=Path,
        default=Path("data/sbert/annotation/20260607_sbert_final_validation/manual_qrels_annotation.csv"),
    )
    parser.add_argument("--qrels-dir", type=Path, default=Path("data/sbert/qrels"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/sbert/gold_qrels"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = build(parse_args(argv))
    print(json.dumps({
        "status": report["status"],
        "silver_judgements": report["silver_qrels"]["n_judgements"],
        "gold_judgements": report["gold_qrels"]["n_judgements"],
        "pending_expert_grade": report["annotation_template"]["n_rows_pending_expert_grade"],
        "kappa": report["gold_qrels"]["inter_annotator_agreement"].get("kappa"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
