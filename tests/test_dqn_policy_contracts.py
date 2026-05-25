"""Contracts for DQN replay, target-network, and policy checkpoint behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.dqn.main import OnlineDQN, RewardUpdateRequest
from services.pipeline.stages.stage_4_dqn_rank import run_dqn_rank_stage


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


def test_dqn_rank_returns_skill_path_policy_metadata() -> None:
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

    assert ranked[0]["policy_source"] == "skill_path_policy"
    assert ranked[0]["policy_objective"] == "skill_path"
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


def test_dqn_rank_metadata_frames_action_as_skill_path_signal() -> None:
    agent = OnlineDQN(load_existing=False, autosave=False)
    agent.epsilon = 0.0

    ranked = agent.rank(
        "u-skill-path-rank",
        [
            {
                "id": "backend",
                "title": "Backend Developer",
                "skills": ["FastAPI", "PostgreSQL"],
                "sbert_score": 0.7,
                "ncf_score": 0.6,
            }
        ],
        {
            "skills": ["Python"],
            "target_role": "Backend Developer",
            "market_demand": {"FastAPI": 0.8, "PostgreSQL": 0.9},
        },
    )

    action = ranked[0]
    assert action["policy_objective"] == "skill_path"
    assert action["action_type"] in {"skill", "course", "certificate", "career_milestone"}
    assert action["action_label"] in {"FastAPI", "PostgreSQL"}
    assert action["reward_components"]["total_reward"] == pytest.approx(
        action["reward_components"]["skill_gap_reduction"]
        + action["reward_components"]["job_match_lift"]
    )
    assert action["skill_gap"] > action["estimated_skill_gap_after"]


@pytest.mark.anyio
async def test_pipeline_dqn_stage_preserves_skill_path_metadata() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "model_version": "online-dqn-v2",
                "ranked": [
                    {
                        "job": {"id": "job-backend"},
                        "q_value": 0.8,
                        "action": 24,
                        "action_label": "FastAPI",
                        "action_type": "career_milestone",
                        "policy_source": "skill_path_policy",
                        "policy_objective": "skill_path",
                        "reward_components": {
                            "skill_gap_reduction": 0.5,
                            "job_match_lift": 0.8,
                            "total_reward": 1.3,
                        },
                        "skill_gap": 0.8,
                        "estimated_skill_gap_after": 0.6,
                        "market_demand": 0.8,
                    }
                ],
            }

    class FakeClient:
        def __init__(self) -> None:
            self.payload = None

        async def post(self, _url, json):
            self.payload = json
            return FakeResponse()

    client = FakeClient()

    result = await run_dqn_rank_stage(
        client,
        "http://dqn",
        {
            "id": "u-pipeline",
            "skills": ["Python"],
            "target_role": "Backend Developer",
            "interaction_count": 3,
        },
        [
            {
                "id": "job-backend",
                "title": "Backend Developer",
                "skills": ["FastAPI"],
                "sbert_score": 0.7,
                "ncf_score": 0.6,
            }
        ],
    )

    assert client.payload["session_ctx"]["target_role"] == "Backend Developer"
    assert result.jobs[0]["dqn_action_type"] == "career_milestone"
    assert result.jobs[0]["dqn_policy_objective"] == "skill_path"
    assert result.jobs[0]["dqn_reward_components"]["total_reward"] == pytest.approx(1.3)
    assert result.jobs[0]["dqn_skill_gap"] == pytest.approx(0.8)
    assert result.jobs[0]["dqn_estimated_skill_gap_after"] == pytest.approx(0.6)
    assert result.summary["policy_objective"] == "skill_path"
