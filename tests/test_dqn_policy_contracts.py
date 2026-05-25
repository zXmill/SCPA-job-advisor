"""Contracts for DQN replay, target-network, and policy checkpoint behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.dqn.main import OnlineDQN, RewardUpdateRequest


def test_dqn_learn_persists_replay_transition_and_target_checkpoint(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "online_dqn.json"
    agent = OnlineDQN(model_path=model_path, load_existing=False)
    job = {
        "id": "job-data",
        "title": "Data Scientist",
        "description": "Build machine learning dashboards",
        "sbert_score": 0.8,
        "ncf_score": 0.7,
    }

    update = agent.learn(
        RewardUpdateRequest(
            user_id="u-dqn",
            job_id=job["id"],
            event="click",
            job=job,
            action="machine learning",
        )
    )
    for _ in range(max(agent.min_replay_size, agent.target_sync_interval)):
        agent.learn(
            RewardUpdateRequest(
                user_id="u-dqn",
                job_id=job["id"],
                event="click",
                job=job,
                action="machine learning",
            )
        )

    agent.save()
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    transition = agent.replay.to_list()[0]

    assert update["policy_source"] == "request_action"
    assert update["action_label"] == "machine learning"
    assert transition.keys() >= {
        "state",
        "action",
        "action_label",
        "reward",
        "next_state",
        "done",
        "policy_source",
        "model_version",
    }
    assert payload["architecture"] == "DQN(QNetwork+ReplayBuffer+target_net)"
    assert payload["epsilon"] < 0.12
    assert agent.checkpoint_path.exists()

    reloaded = OnlineDQN(model_path=model_path, load_existing=True)
    assert len(reloaded.replay) == len(agent.replay)
    assert reloaded.policy_net is not None
    assert reloaded.target_net is not None


def test_dqn_learning_path_returns_policy_metadata() -> None:
    agent = OnlineDQN(load_existing=False, autosave=False)
    agent.epsilon = 0.0
    ranked = agent.rank(
        "u-policy",
        [
            {"id": "backend", "title": "Backend Developer", "sbert_score": 0.4, "ncf_score": 0.8},
            {"id": "mc", "title": "Master of Ceremony", "sbert_score": 0.7, "ncf_score": 0.2},
        ],
        {"interaction_count": 5},
    )

    assert ranked[0]["policy_source"] == "qnetwork_policy"
    assert isinstance(ranked[0]["action"], int)
    assert ranked[0]["action_label"]


def test_dqn_rank_batches_policy_forward_for_multiple_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = OnlineDQN(load_existing=False, autosave=False)
    if agent.policy_net is None:
        pytest.skip("torch unavailable - DQN neural path not testable")

    agent.epsilon = 0.0
    forward_calls = 0
    original_forward = agent.policy_net.forward

    def counted_forward(features):
        nonlocal forward_calls
        forward_calls += 1
        return original_forward(features)

    monkeypatch.setattr(agent.policy_net, "forward", counted_forward)

    agent.rank(
        "u-batch",
        [
            {"id": "backend", "title": "Backend Developer", "sbert_score": 0.4, "ncf_score": 0.8},
            {"id": "data", "title": "Data Analyst", "sbert_score": 0.8, "ncf_score": 0.4},
            {"id": "design", "title": "Product Designer", "sbert_score": 0.5, "ncf_score": 0.5},
        ],
        {"interaction_count": 5},
    )

    assert forward_calls == 1
