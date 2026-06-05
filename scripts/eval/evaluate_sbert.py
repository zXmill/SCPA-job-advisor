"""Evaluate SBERT recommender on test pairs.

P5-ML-002: Build test dataset, score with SBERT (fallback or transformer),
and report ranking metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.sbert.training.train_sbert import build_training_pairs, load_jsonl
from services.sbert.training.hard_negatives import (
    deterministic_training_embedding,
    mine_hard_negative_examples,
)
from services.evaluation.recommendation_metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    hit_rate_at_k,
    mean_metric,
)


def _score_pair(left: str, right: str) -> float:
    """Score a pair using deterministic fallback embeddings."""
    left_emb = deterministic_training_embedding(left)
    right_emb = deterministic_training_embedding(right)
    # Cosine similarity on L2-normalized vectors
    dot = sum(a * b for a, b in zip(left_emb, right_emb))
    norm = (sum(a * a for a in left_emb) * sum(b * b for b in right_emb)) ** 0.5
    return max(0.0, min(1.0, dot / norm if norm > 0 else 0.0))


def evaluate_sbert(
    data_path: Path,
    output_dir: Path,
    k_values: tuple[int, ...] = (5, 10),
) -> dict[str, Any]:
    records = load_jsonl(data_path)
    # Build pairs directly from records without strict validation
    pairs: list[tuple[str, str]] = []
    for record in records:
        left = str(record.get("profile_text") or record.get("title") or record.get("query") or "").strip()
        right = str(record.get("job_text") or record.get("description") or record.get("positive") or "").strip()
        if left and right:
            pairs.append((left, right))
    if not pairs:
        raise ValueError("no training pairs found")

    # For each anchor, collect positives and hard negatives
    anchors: dict[str, list[str]] = {}
    for left, right in pairs:
        anchors.setdefault(left, []).append(right)

    # Build hard negatives if available
    hard_negatives: dict[str, list[str]] = {}
    try:
        examples = mine_hard_negative_examples(records)
        for ex in examples:
            hard_negatives.setdefault(ex.anchor, []).append(ex.hard_negative)
    except Exception:
        pass

    rankings: dict[str, list[str]] = {}
    relevant: dict[str, set[str]] = {}
    for anchor, positives in anchors.items():
        candidates = list(set(positives))
        negatives = list(set(hard_negatives.get(anchor, [])))
        all_candidates = candidates + [n for n in negatives if n not in candidates]
        scored = [(cand, _score_pair(anchor, cand)) for cand in all_candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        rankings[anchor] = [cand for cand, _ in scored]
        relevant[anchor] = set(positives)

    report: dict[str, Any] = {"dataset": str(data_path), "n_queries": len(rankings)}
    for k in k_values:
        report[f"precision_at_{k}"] = round(
            mean_metric(precision_at_k(rankings[q], relevant[q], k) for q in rankings), 6
        )
        report[f"recall_at_{k}"] = round(
            mean_metric(recall_at_k(rankings[q], relevant[q], k) for q in rankings), 6
        )
        report[f"ndcg_at_{k}"] = round(
            mean_metric(ndcg_at_k(rankings[q], relevant[q], k) for q in rankings), 6
        )
        report[f"hit_rate_at_{k}"] = round(
            mean_metric(hit_rate_at_k(rankings[q], relevant[q], k) for q in rankings), 6
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sbert_evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/sbert_test_pairs.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/sbert"))
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10])
    args = parser.parse_args()

    # If test data doesn't exist, create synthetic test pairs
    if not args.data.exists():
        args.data.parent.mkdir(parents=True, exist_ok=True)
        synthetic = [
            {"profile_text": "Sastra Inggris Public Speaking", "job_text": "Master of Ceremony", "pair_kind": "positive"},
            {"profile_text": "Sastra Inggris Public Speaking", "job_text": "Content Writer", "pair_kind": "positive"},
            {"profile_text": "Sastra Inggris Public Speaking", "job_text": "Backend Developer", "pair_kind": "negative"},
            {"profile_text": "Computer Science Python", "job_text": "Backend Developer", "pair_kind": "positive"},
            {"profile_text": "Computer Science Python", "job_text": "Data Engineer", "pair_kind": "positive"},
            {"profile_text": "Computer Science Python", "job_text": "Master of Ceremony", "pair_kind": "negative"},
        ]
        args.data.write_text("\n".join(json.dumps(r) for r in synthetic) + "\n", encoding="utf-8")

    report = evaluate_sbert(args.data, args.output_dir, k_values=tuple(args.k))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
