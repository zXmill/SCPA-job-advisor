"""Train a small DQN checkpoint on deterministic session-reranking rewards."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
from torch import nn

from services.dqn.main import (
    EVENT_REWARDS,
    FEATURE_DIM,
    N_ACTIONS,
    QNetwork,
    SESSION_RERANK_OBJECTIVE,
    reward_value,
)


STATE_DIM = FEATURE_DIM


SESSION_EVENTS = (
    "view",
    "click",
    "valid_dwell",
    "save",
    "apply",
    "skip",
    "ignore",
    "repeated_irrelevant_exposure",
)


def _synthetic_batch() -> tuple[torch.Tensor, torch.Tensor]:
    states: list[list[float]] = []
    targets: list[list[float]] = []
    for idx in range(128):
        state = [0.0] * STATE_DIM
        action_index = idx % N_ACTIONS
        event = SESSION_EVENTS[idx % len(SESSION_EVENTS)]
        base_score = 0.35 + (0.08 * (idx % 5))
        ncf_score = 0.25 + (0.1 * ((idx // 2) % 5))
        history_depth = min(1.0, (idx % 12) / 12.0)
        interaction_depth = min(1.0, ((idx // 3) % 16) / 16.0)
        text_signal = 0.4 + (0.06 * (idx % 6))
        state[-6:] = [base_score, ncf_score, history_depth, interaction_depth, text_signal, 1.0]
        state[action_index % max(1, STATE_DIM - 6)] = 0.75
        if idx % 4 == 0:
            state[(action_index * 7) % max(1, STATE_DIM - 6)] = 1.0

        reward = [-0.02] * N_ACTIONS
        observed_reward = reward_value(event)
        session_target = 0.5 + (0.5 * observed_reward)
        reward[action_index] = session_target
        if event in {"skip", "ignore", "repeated_irrelevant_exposure"}:
            reward[(action_index + 1) % N_ACTIONS] = 0.55
        states.append(state)
        targets.append(reward)
    return torch.tensor(states, dtype=torch.float32), torch.tensor(targets, dtype=torch.float32)


def train(output_dir: Path, steps: int) -> dict[str, Any]:
    torch.manual_seed(7)
    output_dir.mkdir(parents=True, exist_ok=True)
    model = QNetwork(state_dim=STATE_DIM, n_actions=N_ACTIONS)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=1e-4)
    loss_fn = nn.MSELoss()
    states, targets = _synthetic_batch()

    losses: list[float] = []
    for _ in range(max(steps, 0)):
        pred = model(states)
        loss = loss_fn(pred, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    model.eval()
    with torch.inference_mode():
        q_values = model(states)
        chosen = q_values.argmax(dim=1)
        optimal = targets.argmax(dim=1)
        policy_reward = targets[torch.arange(len(states)), chosen].mean().item()
        random_reward = targets.mean(dim=1).mean().item()
        accuracy = (chosen == optimal).float().mean().item()

    checkpoint_path = output_dir / "dqn_model.pt"
    torch.save(model.state_dict(), checkpoint_path)
    metrics = {
        "steps": steps,
        "policy_objective": SESSION_RERANK_OBJECTIVE,
        "mdp": {
            "state": "candidate_features + active_session_history",
            "action": "rank_top_m_job_candidates",
            "reward": "session_behavior:view_click_dwell_save_apply_skip_ignore",
        },
        "reward_schema": {
            key: EVENT_REWARDS[key]
            for key in (
                "view",
                "click",
                "valid_dwell",
                "save",
                "apply",
                "skip",
                "ignore",
                "repeated_irrelevant_exposure",
            )
        },
        "mean_td_error": round(math.sqrt(sum(losses) / len(losses)), 6) if losses else 0.0,
        "policy_accuracy": round(accuracy, 6),
        "validation_reward": round(policy_reward, 6),
        "random_reward": round(random_reward, 6),
        "dqn_reward_lift": round(policy_reward / max(random_reward, 1e-6), 6),
        "checkpoint": str(checkpoint_path),
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(train(args.output_dir, args.steps)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
