"""Train a small NeuralCF checkpoint on deterministic local interactions."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch
from torch import nn

from services.ncf.main import NeuralCF


def ndcg_at_k(ranked: list[int], relevant: set[int], k: int = 5) -> float:
    dcg = 0.0
    for rank, item_id in enumerate(ranked[:k], start=1):
        if item_id in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    if not relevant:
        return 0.0
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def _synthetic_interactions() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    users: list[int] = []
    items: list[int] = []
    labels: list[float] = []
    for user_id in range(16):
        preferred = user_id % 8
        secondary = (preferred + 2) % 8
        for item_id in range(16):
            label = 1.0 if item_id in {preferred, secondary} else 0.0
            users.append(user_id)
            items.append(item_id)
            labels.append(label)
    return (
        torch.tensor(users, dtype=torch.long),
        torch.tensor(items, dtype=torch.long),
        torch.tensor(labels, dtype=torch.float32),
    )


def train(output_dir: Path, steps: int, batch_size: int) -> dict[str, float | int | str]:
    torch.manual_seed(42)
    output_dir.mkdir(parents=True, exist_ok=True)
    model = NeuralCF(num_users=64, num_items=128, embedding_dim=32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    users, items, labels = _synthetic_interactions()

    losses: list[float] = []
    for step in range(max(steps, 0)):
        offset = (step * batch_size) % len(users)
        indices = torch.arange(offset, offset + batch_size) % len(users)
        logits = model(users[indices], items[indices])
        loss = loss_fn(logits, labels[indices])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    model.eval()
    top5_hits: list[float] = []
    ndcgs: list[float] = []
    with torch.inference_mode():
        all_items = torch.arange(16, dtype=torch.long)
        for user_id in range(16):
            user_tensor = torch.full((16,), user_id, dtype=torch.long)
            scores = torch.sigmoid(model(user_tensor, all_items))
            ranked = torch.argsort(scores, descending=True).tolist()
            relevant = {user_id % 8, (user_id % 8 + 2) % 8}
            top5_hits.append(1.0 if relevant.intersection(ranked[:5]) else 0.0)
            ndcgs.append(ndcg_at_k(ranked, relevant, k=5))

    checkpoint_path = output_dir / "ncf_model.pt"
    torch.save(model.state_dict(), checkpoint_path)
    metrics = {
        "steps": steps,
        "mean_loss": round(sum(losses) / len(losses), 6) if losses else 0.0,
        "top5_accuracy": round(sum(top5_hits) / len(top5_hits), 6),
        "ndcg_at_5": round(sum(ndcgs) / len(ndcgs), 6),
        "checkpoint": str(checkpoint_path),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    print(json.dumps(train(args.output_dir, args.steps, args.batch_size)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

