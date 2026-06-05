"""Evaluate fine-tuned SentenceTransformer on Indonesian profile-job pairs.

Reports Recall@K, MRR@K, NDCG@K, and generates qualitative skill-gap examples.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from services.sbert.training.fine_tune_sbert import (
    evaluate_finetuned_model,
    generate_skill_gap_examples,
    fine_tune_sbert,
)


def evaluate_finetuned_sbert(
    data_path: Path,
    model_dir: Path,
    output_dir: Path,
    *,
    k_values: tuple[int, ...] = (5, 10),
    device: str | None = None,
) -> dict[str, Any]:
    """Run full evaluation: ranking metrics + skill-gap examples."""

    report = evaluate_finetuned_model(
        data_path,
        model_dir,
        output_dir,
        k_values=k_values,
        device=device,
    )

    examples = generate_skill_gap_examples(
        data_path,
        model_dir,
        output_dir,
        top_k=max(k_values) if k_values else 5,
        device=device,
    )

    report["skill_gap_examples_count"] = len(examples)
    report["skill_gap_examples_path"] = str(output_dir / "skill_gap_examples.json")

    (output_dir / "finetuned_sbert_full_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("services/sbert/training/data/indonesian_profile_job_pairs.jsonl"))
    parser.add_argument("--model-dir", type=Path, default=Path("services/sbert/models/finetuned_indonesian"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/finetuned_sbert"))
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10])
    parser.add_argument("--device", default=None)
    parser.add_argument("--skip-training", action="store_true", help="Assume model already exists")
    args = parser.parse_args(argv)

    if not args.skip_training and not args.model_dir.exists():
        print("Model not found; running fine-tuning first...")
        fine_tune_sbert(
            args.data,
            args.model_dir,
            epochs=3,
            batch_size=8,
            device=args.device,
        )

    report = evaluate_finetuned_sbert(
        args.data,
        args.model_dir,
        args.output_dir,
        k_values=tuple(args.k),
        device=args.device,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
