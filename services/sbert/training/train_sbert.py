"""Build and validate semantic matching pairs for SBERT-style training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from services.sbert.training.data_preparation import validate_pair_records
from services.sbert.training.hard_negatives import (
    EMBEDDING_DIM,
    HardNegativeExample,
    assert_positive_outranks_negatives,
    deterministic_training_embedding,
    mine_hard_negative_examples,
)


class SimilarityHead(nn.Module):
    """Trainable projection head over frozen SBERT-compatible embeddings."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        super().__init__()
        self.projection = nn.Sequential(
            nn.Linear(dim, dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
        )

    def forward(self, left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
        left_proj = nn.functional.normalize(self.projection(left), dim=-1)
        right_proj = nn.functional.normalize(self.projection(right), dim=-1)
        return (left_proj * right_proj).sum(dim=-1)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_training_pairs(records: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if records and all("profile_text" in record and "job_text" in record for record in records):
        errors = validate_pair_records(records)
        if errors:
            raise ValueError("invalid SBERT training data: " + "; ".join(errors))
        return [
            (str(record["profile_text"]).strip(), str(record["job_text"]).strip())
            for record in records
            if record.get("pair_kind") == "positive"
        ]

    pairs: list[tuple[str, str]] = []
    for record in records:
        title = str(record.get("title") or record.get("query") or "").strip()
        description = str(record.get("description") or record.get("positive") or "").strip()
        if title and description:
            pairs.append((title, description))
    return pairs


def build_hard_negative_training_examples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build serializable same-sector wrong-skill hard-negative rows."""

    examples = mine_hard_negative_examples(records)
    assert_positive_outranks_negatives(examples)
    return [example.to_training_row() for example in examples]


def build_training_triplets(records: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Return ``(anchor, positive, hard_negative)`` rows for ranking training."""

    examples = mine_hard_negative_examples(records)
    assert_positive_outranks_negatives(examples)
    return [
        (example.anchor, example.positive, example.hard_negative)
        for example in examples
    ]


def train_from_pairs(
    pairs: list[tuple[str, str]],
    output_dir: Path,
    *,
    steps: int = 20,
    negative_texts: list[str] | None = None,
) -> dict[str, float | int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not pairs:
        raise ValueError("at least one training pair is required")
    if negative_texts is not None and len(negative_texts) != len(pairs):
        raise ValueError("negative_texts must have the same length as pairs")

    torch.manual_seed(13)
    model = SimilarityHead()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=1e-4)
    positives_left = torch.tensor(
        np.vstack([deterministic_training_embedding(left) for left, _ in pairs]),
        dtype=torch.float32,
    )
    positives_right = torch.tensor(
        np.vstack([deterministic_training_embedding(right) for _, right in pairs]),
        dtype=torch.float32,
    )
    if negative_texts is None:
        negatives_right = positives_right.roll(shifts=1, dims=0)
        negative_source = "rolled_positive"
    else:
        negatives_right = torch.tensor(
            np.vstack([deterministic_training_embedding(text) for text in negative_texts]),
            dtype=torch.float32,
        )
        negative_source = "hard_negative"

    labels = torch.cat([torch.ones(len(pairs)), torch.zeros(len(pairs))])
    left = torch.cat([positives_left, positives_left])
    right = torch.cat([positives_right, negatives_right])
    loss_fn = nn.MSELoss()

    losses: list[float] = []
    for _ in range(max(steps, 0)):
        scores = (model(left, right) + 1.0) / 2.0
        loss = loss_fn(scores, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    model.eval()
    with torch.inference_mode():
        scores = (model(left, right) + 1.0) / 2.0
        positive_scores = scores[: len(pairs)]
        negative_scores = scores[len(pairs) :]
        margin = float((positive_scores - negative_scores).mean().item())
        pair_accuracy = float((positive_scores > negative_scores).float().mean().item())

    checkpoint_path = output_dir / "sbert_similarity_head.pt"
    torch.save(model.state_dict(), checkpoint_path)
    metrics = {
        "steps": steps,
        "pairs": len(pairs),
        "mean_loss": round(sum(losses) / len(losses), 6) if losses else 0.0,
        "pair_accuracy": round(pair_accuracy, 6),
        "semantic_margin": round(margin, 6),
        "negative_source": negative_source,
        "checkpoint": str(checkpoint_path),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def train_from_records(
    records: list[dict[str, Any]],
    output_dir: Path,
    *,
    steps: int = 20,
) -> dict[str, float | int | str]:
    """Train using mined hard negatives when source records support them."""

    examples = mine_hard_negative_examples(records)
    if not examples:
        return train_from_pairs(build_training_pairs(records), output_dir, steps=steps)

    contract_metrics = assert_positive_outranks_negatives(examples)
    _write_hard_negative_examples(output_dir, examples)
    metrics = train_from_pairs(
        [(example.anchor, example.positive) for example in examples],
        output_dir,
        steps=steps,
        negative_texts=[example.hard_negative for example in examples],
    )
    metrics.update(contract_metrics)
    metrics["hard_negative_contract"] = "same-sector-wrong-skill"
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def _write_hard_negative_examples(output_dir: Path, examples: list[HardNegativeExample]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(example.to_training_row(), sort_keys=True) for example in examples]
    (output_dir / "hard_negatives.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(train_from_records(load_jsonl(args.data), args.output_dir, steps=args.steps)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
