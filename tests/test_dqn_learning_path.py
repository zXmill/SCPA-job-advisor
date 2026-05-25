"""Regression tests for DQN career-action recommendations."""

from __future__ import annotations

import pytest

from services.dqn.main import LearningPathRequest, agent, learning_path


@pytest.fixture(autouse=True)
def _freeze_epsilon():
    """Freeze epsilon to 0 so policy tests are deterministic."""
    old = agent.epsilon
    agent.epsilon = 0.0
    yield
    agent.epsilon = old


@pytest.mark.anyio
async def test_dqn_learning_path_returns_policy_steps() -> None:
    response = await learning_path(
        LearningPathRequest(
            user_id="u-design-test",
            current_skills=["Figma", "UI Design", "Prototyping"],
            target_role="UI/UX Designer",
        )
    )

    skills = [step["skill"] for step in response["learning_path"]]

    assert response["total_steps"] >= 1
    assert len(skills) == response["total_steps"]
    assert all(isinstance(step.get("skill"), str) for step in response["learning_path"])
    assert all(
        step.get("policy_source") in {"qnetwork_policy", "epsilon_explore", "fallback", "skill_path_policy"}
        for step in response["learning_path"]
    )


@pytest.mark.anyio
async def test_dqn_learning_path_excludes_mastered_skills() -> None:
    mastered = ["Python", "SQL", "Statistics", "Pandas"]
    response = await learning_path(
        LearningPathRequest(
            user_id="u-data-test",
            current_skills=mastered,
            target_role="Data Scientist",
        )
    )

    skills = [step["skill"] for step in response["learning_path"]]

    assert response["total_steps"] >= 1
    for skill in skills:
        assert skill.lower() not in {s.lower() for s in mastered}


@pytest.mark.anyio
async def test_dqn_learning_path_exposes_skill_path_mdp_and_reward_components() -> None:
    response = await learning_path(
        LearningPathRequest(
            user_id="u-gap-test",
            current_skills=["Python", "Pandas"],
            target_role="Data Scientist",
            market_demand={
                "SQL": 0.95,
                "Machine Learning": 0.65,
                "Statistics": 0.7,
                "Dashboard": 0.2,
            },
        )
    )

    assert response["policy_objective"] == "skill_path"
    assert response["mdp"]["action_space"] == "next_skill_course_certificate_or_career_milestone"
    assert response["mdp"]["reward"] == "skill_gap_reduction + job_match_lift"
    assert response["mdp"]["state"]["user_profile"]["target_role"] == "Data Scientist"
    assert response["mdp"]["state"]["missing_skills"] == [
        "Machine Learning",
        "Statistics",
        "SQL",
        "Dashboard",
    ]
    assert response["mdp"]["state"]["market_demand"]["SQL"] == pytest.approx(0.95)

    first_step = response["learning_path"][0]
    assert first_step["skill"] == "SQL"
    assert first_step["action_type"] in {"skill", "course", "certificate", "career_milestone"}
    assert "job" not in first_step
    assert "job_id" not in first_step
    assert first_step["reward_components"]["total_reward"] == pytest.approx(
        first_step["reward_components"]["skill_gap_reduction"]
        + first_step["reward_components"]["job_match_lift"]
    )
    assert first_step["estimated_skill_gap_after"] < response["mdp"]["state"]["skill_gap"]
