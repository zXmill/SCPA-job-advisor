"""Tune hybrid NCF/SBERT/DQN weights against validation NDCG."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


def ndcg_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int = 5) -> float:
    dcg = 0.0
    for rank, item_id in enumerate(ranked_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant_ids), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def _session_ndcg(session: dict[str, Any], weights: tuple[float, float, float]) -> float:
    alpha, beta, gamma = weights
    fused = [
        alpha * ncf + beta * sbert + gamma * dqn
        for ncf, sbert, dqn in zip(
            session.get("ncf_scores", []),
            session.get("sbert_scores", []),
            session.get("dqn_scores", []),
        )
    ]
    ranked = sorted(range(len(fused)), key=lambda idx: fused[idx], reverse=True)
    return ndcg_at_k(ranked, set(session.get("applied_ids", [])), k=5)


def tune_weights(sessions: list[dict[str, Any]]) -> dict[str, float]:
    """Grid-search normalized weights and return thesis-aligned validation metrics."""
    if not sessions:
        return {
            "alpha_ncf": 1 / 3,
            "beta_sbert": 1 / 3,
            "gamma_dqn": 1 / 3,
            "validation_ndcg": 0.0,
        }

    best_weights = (1 / 3, 1 / 3, 1 / 3)
    best_score = -1.0
    for ncf_i in range(0, 11):
        for sbert_i in range(0, 11 - ncf_i):
            dqn_i = 10 - ncf_i - sbert_i
            weights = (ncf_i / 10, sbert_i / 10, dqn_i / 10)
            score = mean(_session_ndcg(session, weights) for session in sessions)
            if score > best_score:
                best_score = score
                best_weights = weights

    alpha, beta, gamma = best_weights
    return {
        "alpha_ncf": round(alpha, 4),
        "beta_sbert": round(beta, 4),
        "gamma_dqn": round(gamma, 4),
        "validation_ndcg": round(best_score, 6),
    }


def _load_sessions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("hybrid tuning data must be a list of sessions")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    sessions = _load_sessions(args.data) if args.data else []
    print(json.dumps(tune_weights(sessions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

