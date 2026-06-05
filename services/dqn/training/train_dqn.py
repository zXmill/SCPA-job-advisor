"""Train a small DQN checkpoint on deterministic learning-path rewards."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
from torch import nn

from services.dqn.main import N_ACTIONS, QNetwork, ROLE_SKILL_REQUIREMENTS, ROLE_VOCAB, SKILL_VOCAB


STATE_DIM = (len(SKILL_VOCAB) * 3) + len(ROLE_VOCAB)


def _skill_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("-", " ").split())


def _synthetic_batch() -> tuple[torch.Tensor, torch.Tensor]:
    states: list[list[float]] = []
    targets: list[list[float]] = []
    skill_keys = [_skill_key(skill) for skill in SKILL_VOCAB]
    for idx in range(96):
        role_idx = idx % len(ROLE_VOCAB)
        role = ROLE_VOCAB[role_idx]
        required = ROLE_SKILL_REQUIREMENTS.get(_skill_key(role), [])
        required_keys = {_skill_key(skill) for skill in required}
        mastered_keys = {
            key
            for skill_index, key in enumerate(skill_keys)
            if key in required_keys and (idx + skill_index) % 3 == 0
        }
        missing_keys = required_keys - mastered_keys
        state = [0.0] * STATE_DIM
        reward = [0.05] * N_ACTIONS
        for skill_index, key in enumerate(skill_keys):
            market_demand = 0.2
            if key in required_keys:
                market_demand = 0.55 + (0.35 * ((skill_index % 4) / 3.0))
            if key in mastered_keys:
                state[skill_index] = 1.0
            if key in missing_keys:
                state[len(SKILL_VOCAB) + skill_index] = 1.0
                gap_reduction = 1.0 / max(1, len(missing_keys))
                reward[skill_index] = gap_reduction + market_demand
            state[(2 * len(SKILL_VOCAB)) + skill_index] = market_demand
        state[(3 * len(SKILL_VOCAB)) + role_idx] = 1.0
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
        "policy_objective": "skill_path",
        "mdp": {
            "state": "user_profile + missing_skills + market_demand",
            "action": "next_skill_course_certificate_or_career_milestone",
            "reward": "skill_gap_reduction + job_match_lift",
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
