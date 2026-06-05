"""Regression tests for the active DQN session reranker contract."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.dqn.main import RerankRequest, agent, app as dqn_app, rerank, reward_value


LEGACY_RESPONSE_FIELDS = {
    "learning_path",
    "career_path",
    "skill_path",
    "market_demand",
    "estimated_skill_gap_after",
    "next_milestone",
    "recommended_milestones",
    "skill_gap_reduction",
}


@pytest.fixture(autouse=True)
def _freeze_epsilon():
    old = agent.epsilon
    agent.epsilon = 0.0
    yield
    agent.epsilon = old


@pytest.mark.anyio
async def test_dqn_rerank_returns_ranked_job_candidates() -> None:
    response = await rerank(
        RerankRequest(
            user_id="u-session-test",
            session_id="session-1",
            session_events=[{"event": "click", "job_id": "job-api"}],
            session_history=[{"event": "click", "job_id": "job-api"}],
            candidates=[
                {
                    "id": "job-data",
                    "title": "Data Analyst",
                    "base_score": 0.7,
                    "ncf_score": 0.61,
                },
                {
                    "id": "job-api",
                    "title": "Backend API Engineer",
                    "base_score": 0.72,
                    "ncf_score": 0.63,
                },
            ],
        )
    )

    assert response["policy_objective"] == "session_rerank"
    assert response["session_id"] == "session-1"
    assert response["metadata"]["input_candidate_count"] == 2
    assert response["metadata"]["model"] == "dqn_session_reranker"

    ranked_jobs = response["ranked_jobs"]
    assert len(ranked_jobs) == 2
    assert {job["rank"] for job in ranked_jobs} == {1, 2}
    job_ids = {job["job_id"] for job in ranked_jobs}
    assert job_ids == {"job-api", "job-data"}
    assert all(0.0 <= job["dqn_session_score"] <= 1.0 for job in ranked_jobs)
    assert ranked_jobs[0]["job_id"] == "job-api"
    assert ranked_jobs[0]["rerank_reason"] in {"qnetwork_session_policy", "session_click_signal"}
    required = ("base_score", "ncf_score", "dqn_session_score", "rank", "rerank_reason", "dqn_mode", "policy_objective", "reward_trace")
    for required_field in required:
        assert required_field in ranked_jobs[0], required_field
    assert ranked_jobs[0]["policy_objective"] == "session_rerank"
    assert ranked_jobs[0]["dqn_mode"] == "session_rerank"
    assert "final_score" not in ranked_jobs[0]
    assert "final_score" not in response

    assert not (LEGACY_RESPONSE_FIELDS & response.keys())
    for item in ranked_jobs:
        assert not (LEGACY_RESPONSE_FIELDS & item.keys())


@pytest.mark.anyio
async def test_dqn_rerank_empty_candidates_returns_http_200_shape() -> None:
    response = await rerank(
        RerankRequest(
            user_id="u-empty",
            session_id="session-empty",
            candidates=[],
        )
    )

    assert response["policy_objective"] == "session_rerank"
    assert response["ranked_jobs"] == []
    assert response["metadata"]["input_candidate_count"] == 0
    assert response["metadata"]["output_candidate_count"] == 0


def test_dqn_reward_function_uses_session_behavior() -> None:
    assert 0.0 < reward_value("view") < reward_value("click")
    assert reward_value("click") < reward_value("save")
    assert reward_value("save") < reward_value("apply")
    assert reward_value("valid_dwell") > reward_value("view")
    assert reward_value("skip") < 0
    assert reward_value("repeated_irrelevant_exposure") < 0


def test_dqn_legacy_path_endpoint_is_gone() -> None:
    client = TestClient(dqn_app)
    response = client.post("/learning-path", json={"user_id": "u"})

    assert response.status_code == 410
    assert "rank" in response.json()["detail"].lower()
