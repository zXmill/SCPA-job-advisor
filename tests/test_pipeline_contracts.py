"""Pipeline contract tests for provenance, ablation, and feedback context."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

import services.pipeline.main as pipeline_main
from services.pipeline.main import FeedbackRequest, PipelineRunRequest


@pytest.mark.anyio
async def test_pipeline_run_emits_run_provenance_and_served_slate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_scrape(**_kwargs):
        return SimpleNamespace(
            user={"id": "u-pipe", "interaction_count": 30, "profile_text": "Python backend"},
            jobs=[{"id": "job-1", "title": "Backend Developer"}],
            summary={"source": "unit", "returned_jobs": 1},
        )

    async def fake_encode(_client, _url, user, jobs):
        return SimpleNamespace(
            jobs=[{**jobs[0], "sbert_score": 0.8, "embedding": [0.1, 0.2]}],
            summary={
                "model_name": "unit-sbert",
                "model_version": "embedding-cosine",
                "embedding_dim": 2,
                "fallback_flags": [],
            },
        )

    async def fake_ncf(_client, _url, _user, jobs):
        return SimpleNamespace(
            jobs=[{**jobs[0], "ncf_score": 0.7}],
            summary={"model_version": "online-ncf-v2", "fallback_flags": []},
        )

    async def fake_dqn(_client, _url, _user, jobs):
        return SimpleNamespace(
            jobs=[
                {
                    **jobs[0],
                    "dqn_score": 0.6,
                    "dqn_session_score": 0.6,
                    "dqn_rerank_reason": "session_click_signal",
                    "dqn_policy_source": "qnetwork_session_policy",
                    "dqn_policy_objective": "session_rerank",
                }
            ],
            summary={
                "model_version": "online-dqn-v2",
                "policy_objective": "session_rerank",
                "policy_sources": ["qnetwork_session_policy"],
                "rerank_reasons": ["session_click_signal"],
            },
        )

    monkeypatch.setattr(pipeline_main, "http_client", object())
    monkeypatch.setattr(pipeline_main, "run_scrape_stage", fake_scrape)
    monkeypatch.setattr(pipeline_main, "run_encode_stage", fake_encode)
    monkeypatch.setattr(pipeline_main, "run_ncf_score_stage", fake_ncf)
    monkeypatch.setattr(pipeline_main, "run_dqn_rank_stage", fake_dqn)

    response = await pipeline_main.run_pipeline(
        PipelineRunRequest(user_id="u-pipe", limit=1)
    )
    first = response.ranked[0]

    assert response.run_id.startswith("pipe-")
    assert first["run_id"] == response.run_id
    assert first["served_slate_id"] == response.run_id
    assert first["rank"] == 1
    assert first["model_provenance"]["sbert"]["model_name"] == "unit-sbert"
    assert first["model_provenance"]["dqn"]["policy_objective"] == "session_rerank"
    assert first["model_provenance"]["dqn"]["policy_sources"] == ["qnetwork_session_policy"]
    assert first["ablation_scores"]["full"] == first["final_score"]
    assert first["dqn_rerank_reason"] == "session_click_signal"


@pytest.mark.anyio
async def test_pipeline_feedback_preserves_served_slate_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def post(self, url, json):
            if url.endswith("/encode"):
                return FakeResponse({"embeddings": [[0.1, 0.2], [0.2, 0.1]]})
            if url.endswith("/feedback"):
                return FakeResponse({"status": "trained", "feedback_events": 1})
            if url.endswith("/reward"):
                return FakeResponse({"status": "trained", "replay_size": 1})
            raise AssertionError(url)

    monkeypatch.setattr(pipeline_main, "http_client", FakeClient())

    result = await pipeline_main.feedback(
        FeedbackRequest(
            user_id="u-pipe",
            job_id="job-1",
            event="click",
            run_id="pipe-test",
            served_slate_id="pipe-test",
            rank=2,
            profile={"program_studi": "Teknik Informatika", "skills": ["Python"]},
            job={"id": "job-1", "title": "Backend Developer"},
        )
    )

    assert result["slate_context"] == {
        "pipeline_run_id": "pipe-test",
        "served_slate_id": "pipe-test",
        "rank": 2,
    }
    assert result["ncf"]["status"] == "trained"
    assert result["dqn"]["status"] == "trained"


@pytest.mark.anyio
async def test_pipeline_feedback_handles_missing_profile_without_sbert_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, payload, *, fail: bool = False):
            self.payload = payload
            self.fail = fail

        def raise_for_status(self) -> None:
            if self.fail:
                request = httpx.Request("POST", "http://sbert/encode")
                response = httpx.Response(400, request=request, json={"detail": "texts cannot contain empty strings"})
                raise httpx.HTTPStatusError("bad request", request=request, response=response)

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self):
            self.encode_payloads = []
            self.feedback_payload = None

        async def post(self, url, json):
            if url.endswith("/encode"):
                self.encode_payloads.append(json)
                return FakeResponse({"embeddings": []}, fail=True)
            if url.endswith("/feedback"):
                self.feedback_payload = json
                return FakeResponse({"status": "trained", "feedback_events": 1})
            if url.endswith("/reward"):
                return FakeResponse({"status": "trained", "replay_size": 1})
            raise AssertionError(url)

    fake_client = FakeClient()
    monkeypatch.setattr(pipeline_main, "http_client", fake_client)

    result = await pipeline_main.feedback(
        FeedbackRequest(
            user_id="u-empty",
            job_id="job-empty",
            event="impression",
            rank=0,
        )
    )

    assert fake_client.encode_payloads == [{"texts": ["user u-empty"]}]
    assert fake_client.feedback_payload["profile_text"] == "user u-empty"
    assert fake_client.feedback_payload["user_embedding"] == []
    assert result["status"] == "trained"
    assert result["embedding_status"] == "unavailable"
