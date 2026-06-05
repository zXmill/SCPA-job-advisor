"""Evaluate NeuMF recommender with train/test split.

P5-ML-003: Build train/test split, add negative sampling, train NCF,
evaluate on held-out test set, report ranking metrics.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
from torch import nn

from services.evaluation.recommendation_metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    hit_rate_at_k,
    mean_metric,
)


class _NeuralCF(nn.Module):
    """Minimal GMF + MLP model for offline evaluation."""

    def __init__(
        self,
        num_users: int,
        num_items: int,
        embedding_dim: int = 64,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()
        self.user_gmf = nn.Embedding(num_users, embedding_dim)
        self.item_gmf = nn.Embedding(num_items, embedding_dim)
        self.user_mlp = nn.Embedding(num_users, embedding_dim)
        self.item_mlp = nn.Embedding(num_items, embedding_dim)
        self.mlp = nn.Sequential(
            nn.Linear(embedding_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
        )
        self.out = nn.Linear(embedding_dim + hidden_dim // 2, 1)

    def forward(self, user_ids, item_ids):
        gmf = self.user_gmf(user_ids) * self.item_gmf(item_ids)
        mlp = self.mlp(torch.cat([self.user_mlp(user_ids), self.item_mlp(item_ids)], dim=-1))
        return self.out(torch.cat([gmf, mlp], dim=-1)).squeeze(-1)


def _synthetic_interactions(num_users: int = 32, num_items: int = 64) -> tuple[list[tuple[int, int, float]], list[tuple[int, int, float]]]:
    """Generate synthetic train/test interactions with a preference pattern."""
    all_data: list[tuple[int, int, float]] = []
    for user_id in range(num_users):
        preferred = user_id % (num_items // 2)
        secondary = (preferred + 3) % (num_items // 2)
        for item_id in range(num_items):
            label = 1.0 if item_id in {preferred, secondary} else 0.0
            all_data.append((user_id, item_id, label))

    # Shuffle deterministically
    torch.manual_seed(42)
    indices = torch.randperm(len(all_data)).tolist()
    split = int(len(all_data) * 0.8)
    train = [all_data[i] for i in indices[:split]]
    test = [all_data[i] for i in indices[split:]]
    return train, test


def _add_negatives(interactions: list[tuple[int, int, float]], num_users: int, num_items: int, ratio: float = 4.0) -> list[tuple[int, int, float]]:
    """Add random negative samples to balance the dataset."""
    positives = [row for row in interactions if row[2] == 1.0]
    n_neg = min(int(len(positives) * ratio), num_users * num_items - len(interactions))
    negatives: list[tuple[int, int, float]] = []
    seen = {(u, i) for u, i, _ in interactions}
    attempts = 0
    max_attempts = n_neg * 10 + 1000
    while len(negatives) < n_neg and attempts < max_attempts:
        attempts += 1
        u = hash(f"neg_u_{attempts}") % num_users
        i = hash(f"neg_i_{attempts}") % num_items
        if (u, i) not in seen:
            negatives.append((u, i, 0.0))
            seen.add((u, i))
    return positives + negatives


def evaluate_ncf(
    output_dir: Path,
    num_users: int = 32,
    num_items: int = 64,
    embedding_dim: int = 32,
    steps: int = 30,
    batch_size: int = 32,
    k_values: tuple[int, ...] = (5, 10),
) -> dict[str, Any]:
    train_raw, test_raw = _synthetic_interactions(num_users, num_items)
    train_data = _add_negatives(train_raw, num_users, num_items)

    model = _NeuralCF(num_users=num_users, num_items=num_items, embedding_dim=embedding_dim)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()

    users = torch.tensor([u for u, _, _ in train_data], dtype=torch.long)
    items = torch.tensor([i for _, i, _ in train_data], dtype=torch.long)
    labels = torch.tensor([l for _, _, l in train_data], dtype=torch.float32)

    for step in range(steps):
        offset = (step * batch_size) % len(users)
        indices = torch.arange(offset, offset + batch_size) % len(users)
        logits = model(users[indices], items[indices])
        loss = loss_fn(logits, labels[indices])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # Evaluate on test set: for each user, rank all items and check if preferred items are in top-k
    test_users = sorted({u for u, _, l in test_raw if l == 1.0})
    test_relevant: dict[str, set[str]] = {}
    rankings: dict[str, list[str]] = {}
    model.eval()
    with torch.inference_mode():
        all_items = torch.arange(num_items, dtype=torch.long)
        for user_id in test_users:
            user_tensor = torch.full((num_items,), user_id, dtype=torch.long)
            scores = torch.sigmoid(model(user_tensor, all_items))
            ranked = torch.argsort(scores, descending=True).tolist()
            rankings[str(user_id)] = [str(i) for i in ranked]
            relevant = {str(i) for u, i, l in test_raw if u == user_id and l == 1.0}
            if relevant:
                test_relevant[str(user_id)] = relevant

    report: dict[str, Any] = {
        "dataset": "synthetic_interactions",
        "num_users": num_users,
        "num_items": num_items,
        "embedding_dim": embedding_dim,
        "steps": steps,
        "batch_size": batch_size,
        "n_queries": len(test_relevant),
    }
    for k in k_values:
        report[f"precision_at_{k}"] = round(
            mean_metric(precision_at_k(rankings[q], test_relevant[q], k) for q in test_relevant), 6
        )
        report[f"recall_at_{k}"] = round(
            mean_metric(recall_at_k(rankings[q], test_relevant[q], k) for q in test_relevant), 6
        )
        report[f"ndcg_at_{k}"] = round(
            mean_metric(ndcg_at_k(rankings[q], test_relevant[q], k) for q in test_relevant), 6
        )
        report[f"hit_rate_at_{k}"] = round(
            mean_metric(hit_rate_at_k(rankings[q], test_relevant[q], k) for q in test_relevant), 6
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ncf_evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/ncf"))
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10])
    args = parser.parse_args()
    report = evaluate_ncf(args.output_dir, steps=args.steps, batch_size=args.batch_size, k_values=tuple(args.k))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
