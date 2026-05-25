"""Telemetry contracts for pipeline stage latency summaries."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import services.pipeline.main as pipeline_main
from services.pipeline.main import PipelineRunRequest


@pytest.mark.anyio
async def test_pipeline_run_emits_stage_latency_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_scrape(**_kwargs):
        return SimpleNamespace(
            user={"id": "u-telemetry", "interaction_count": 10},
            jobs=[{"id": "job-1", "title": "Backend Developer"}],
            summary={"source": "unit", "returned_jobs": 1},
        )

    async def fake_encode(_client, _url, _user, jobs):
        return SimpleNamespace(
            jobs=[{**jobs[0], "sbert_score": 0.8, "embedding": [0.1, 0.2]}],
            summary={"fallback_flags": [], "model_name": "unit-sbert"},
        )

    async def fake_ncf(_client, _url, _user, jobs):
        return SimpleNamespace(
            jobs=[{**jobs[0], "ncf_score": 0.7}],
            summary={"model_version": "unit-ncf"},
        )

    async def fake_dqn(_client, _url, _user, jobs):
        return SimpleNamespace(
            jobs=[{**jobs[0], "dqn_score": 0.6}],
            summary={"model_version": "unit-dqn", "policy_sources": ["unit"]},
        )

    async def fake_aggregate(_user, jobs):
        return SimpleNamespace(
            ranked=[{**jobs[0], "final_score": 0.75, "ablation_scores": {"full": 0.75}}],
            summary={"strategy": "unit"},
        )

    monkeypatch.setattr(pipeline_main, "http_client", object())
    monkeypatch.setattr(pipeline_main, "run_scrape_stage", fake_scrape)
    monkeypatch.setattr(pipeline_main, "run_encode_stage", fake_encode)
    monkeypatch.setattr(pipeline_main, "run_ncf_score_stage", fake_ncf)
    monkeypatch.setattr(pipeline_main, "run_dqn_rank_stage", fake_dqn)
    monkeypatch.setattr(pipeline_main, "run_aggregate_stage", fake_aggregate)

    response = await pipeline_main.run_pipeline(
        PipelineRunRequest(user_id="u-telemetry", limit=1)
    )

    telemetry = response.stages["telemetry"]["stages"]
    assert set(telemetry) == {"scrape", "sbert", "ncf", "dqn", "calibrator", "aggregation"}
    for stats in telemetry.values():
        assert stats["count"] >= 1
        assert stats["last_ms"] >= 0
        assert stats["p50_ms"] >= 0
        assert stats["p95_ms"] >= stats["p50_ms"]

    assert response.timings_ms["calibrator"] == 0.0
    assert response.stages["calibrator"]["mode"] == "static_baseline"
