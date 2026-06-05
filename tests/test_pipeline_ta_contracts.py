"""TA contract tests for SBERT candidates, DQN rerank metadata, and hybrid scoring."""

from __future__ import annotations

import pytest

from services.pipeline.stages.stage_2_encode import run_encode_stage
from services.pipeline.stages.stage_4_dqn_rank import run_dqn_rank_stage
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[dict[str, object]] = []

    async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        self.requests.append({"url": url, "json": json})
        return FakeResponse(self.payload)


def _jobs() -> list[dict[str, object]]:
    return [
        {"id": "job-a", "title": "Backend Python", "description": "Build Python APIs"},
        {"id": "job-b", "title": "Data Analyst", "description": "Build dashboards"},
        {"id": "job-c", "title": "Sales", "description": "Manage accounts"},
    ]


@pytest.mark.anyio
async def test_stage_2_sbert_emits_semantic_candidate_generator_contract() -> None:
    client = FakeClient(
        {
            "embeddings": [
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [-1.0, 0.0],
            ],
            "model_name": "unit-sbert",
            "model_version": "unit-v1",
            "embedding_dim": 2,
        }
    )

    result = await run_encode_stage(
        client,
        "http://sbert",
        {"profile_text": "Python backend"},
        _jobs(),
    )

    assert [job["job_id"] for job in result.jobs] == ["job-a", "job-b", "job-c"]
    assert [job["semantic_rank"] for job in result.jobs] == [1, 2, 3]
    assert {job["candidate_pool_size"] for job in result.jobs} == {3}
    assert {job["candidate_pool_source"] for job in result.jobs} == {"sbert_top_m"}
    assert result.summary["stage_name"] == "sbert_semantic_candidate_generator"
    assert result.summary["top_m"] == 3
    assert result.summary["input_job_count"] == 3
    assert result.summary["output_candidate_count"] == 3
    assert result.summary["embedding_model"] == "unit-sbert"
    assert result.summary["semantic_metrics"]["metrics_status"] == "not_computed_no_ground_truth"


@pytest.mark.anyio
async def test_stage_2_sbert_computes_metrics_only_with_ground_truth() -> None:
    client = FakeClient(
        {
            "embeddings": [
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [-1.0, 0.0],
            ],
        }
    )

    result = await run_encode_stage(
        client,
        "http://sbert",
        {"profile_text": "Python backend", "relevant_job_ids": ["job-b"]},
        _jobs(),
    )

    metrics = result.summary["semantic_metrics"]
    assert metrics["metrics_status"] == "computed"
    assert metrics["Recall@50"] == 1.0
    assert metrics["Recall@100"] == 1.0
    assert metrics["MRR@10"] == pytest.approx(0.5)
    assert {"NDCG@10", "NDCG@50", "MAP@100"} <= set(metrics)


@pytest.mark.anyio
async def test_stage_4_dqn_cold_start_disables_dqn_signal_and_removes_legacy_fields() -> None:
    class NoCallClient:
        async def post(self, *_args, **_kwargs):  # pragma: no cover - failure path
            raise AssertionError("cold start must not call DQN reranker")

    result = await run_dqn_rank_stage(
        NoCallClient(),
        "http://dqn",
        {"id": "u-cold", "interaction_count": 0},
        [
            {"id": "job-a", "sbert_score": 0.7, "ncf_score": 0.2, "candidate_pool_source": "sbert_top_m"},
            {"id": "job-b", "sbert_score": 0.5, "ncf_score": 0.9, "candidate_pool_source": "sbert_top_m"},
        ],
    )

    first = result.jobs[0]
    assert result.summary["dqn_mode"] == "disabled_cold_start"
    assert {job["dqn_mode"] for job in result.jobs} == {"disabled_cold_start"}
    assert {job["dqn_session_score"] for job in result.jobs} == {0.0}
    assert first["rank_before_dqn"] == 1
    assert first["rank_after_dqn"] == 1
    assert first["candidate_pool_source"]["stage_2"] == "sbert_semantic_candidate_generator"
    assert first["candidate_pool_source"]["stage_3"] == "ncf_interaction_reranker"
    assert first["reward_trace"]["reason"] == "cold_start_without_session_events"
    forbidden = {"dqn_skill_gap", "dqn_market_demand", "dqn_estimated_skill_gap_after"}
    assert forbidden.isdisjoint(first)


@pytest.mark.anyio
async def test_stage_4_dqn_session_adapter_preserves_rank_trace() -> None:
    client = FakeClient(
        {
            "metadata": {"model_version": "session-reranker-v1"},
            "ranked_jobs": [
                {
                    "job_id": "job-b",
                    "dqn_session_score": 0.91,
                    "rank": 1,
                    "reward_trace": [{"event": "click", "reward": 1.0}],
                    "dqn_mode": "session_rerank",
                },
                {
                    "job_id": "job-a",
                    "dqn_session_score": 0.32,
                    "rank": 2,
                    "reward_trace": [{"event": "skip", "reward": -0.1}],
                    "dqn_mode": "session_rerank",
                },
            ],
        }
    )

    result = await run_dqn_rank_stage(
        client,
        "http://dqn",
        {
            "id": "u-session",
            "interaction_count": 4,
            "session_history": [{"job_id": "job-b", "event": "click"}],
        },
        [
            {"id": "job-a", "sbert_score": 0.9, "ncf_score": 0.5, "candidate_pool_source": "sbert_top_m"},
            {"id": "job-b", "sbert_score": 0.7, "ncf_score": 0.7, "candidate_pool_source": "sbert_top_m"},
        ],
    )

    assert client.requests[0]["url"] == "http://dqn/rerank"
    payload = client.requests[0]["json"]
    assert payload["session_ctx"]["reranker_contract"] == "session_rerank_v1"
    assert payload["job_candidates"][0]["candidate_pool_source"]["stage_3"] == "ncf_interaction_reranker"
    assert [job["id"] for job in result.jobs] == ["job-b", "job-a"]
    assert result.jobs[0]["rank_before_dqn"] == 2
    assert result.jobs[0]["rank_after_dqn"] == 1
    assert result.jobs[0]["dqn_session_score"] == pytest.approx(0.91)
    assert result.jobs[0]["dqn_mode"] == "session_rerank"
    assert result.summary["model_version"] == "session-reranker-v1"


@pytest.mark.anyio
async def test_stage_5_transparent_formula_and_cold_start_zero_gamma() -> None:
    result = await run_aggregate_stage(
        {"id": "u-cold", "interaction_count": 0},
        [
            {
                "id": "job-a",
                "sbert_score": 0.5,
                "ncf_score": 0.5,
                "dqn_session_score": 1.0,
                "dqn_mode": "disabled_cold_start",
                "rank_before_dqn": 1,
                "rank_after_dqn": 1,
                "candidate_pool_source": "sbert_ncf_top_m",
            }
        ],
    )

    item = result.ranked[0]
    assert item["alpha"] == 0.8
    assert item["beta"] == 0.2
    assert item["gamma"] == 0.0
    assert result.summary["weights_sum"] == 1.0
    assert item["final_score"] == pytest.approx(0.5)
    assert item["scoring_formula"] == "final_score = alpha*sbert_score + beta*ncf_score + gamma*dqn_session_score"
    assert item["calibrated_score"] != item["final_score"]


@pytest.mark.anyio
async def test_stage_5_active_session_reports_alpha_beta_gamma_formula() -> None:
    result = await run_aggregate_stage(
        {"id": "u-active", "interaction_count": 30},
        [
            {
                "id": "job-a",
                "sbert_score": 0.4,
                "ncf_score": 0.5,
                "dqn_session_score": 0.9,
                "dqn_mode": "session_rerank",
                "rank_before_dqn": 2,
                "rank_after_dqn": 1,
                "candidate_pool_source": "sbert_ncf_top_m",
            }
        ],
    )

    item = result.ranked[0]
    assert (item["alpha"], item["beta"], item["gamma"]) == (0.45, 0.35, 0.2)
    assert item["final_score"] == pytest.approx((0.45 * 0.4) + (0.35 * 0.5) + (0.2 * 0.9))
    assert item["scoring_mode"] == "active_session"
    assert item["final_rank"] == 1
