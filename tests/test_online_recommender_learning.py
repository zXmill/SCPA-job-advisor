import asyncio
from pathlib import Path

from services.dqn.main import OnlineDQN, RewardUpdateRequest
from services.ncf.main import FeedbackEvent, NCFRequest, OnlineNCF
from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.sbert.main import sbert_score


def test_sbert_cold_start_semantics():
    assert sbert_score("Sastra Inggris Public Speaking", "Master of Ceremony") > 0.6
    assert sbert_score("Sastra Inggris Public Speaking", "Backend Developer") < 0.4


def test_online_ncf_learns_from_feedback():
    model = OnlineNCF(autosave=False, load_existing=False)
    user_id = "test-online-ncf"
    profile = "Sastra Inggris Public Speaking"
    before_mc = model.predict_one(user_id, "test-job-mc", profile_text=profile)
    before_backend = model.predict_one(user_id, "test-job-backend", profile_text=profile)

    for _ in range(20):
        model.learn_one(user_id, "test-job-mc", 1.0, profile_text=profile)
        model.learn_one(user_id, "test-job-backend", 0.0, profile_text=profile)

    after_mc = model.predict_one(user_id, "test-job-mc", profile_text=profile)
    after_backend = model.predict_one(user_id, "test-job-backend", profile_text=profile)

    assert after_mc > before_mc
    assert after_backend < before_backend
    scores = model.recommend(
        NCFRequest(
            user_id=user_id,
            profile_text=profile,
            candidates=[
                {"id": "test-job-mc", "title": "Master of Ceremony"},
                {"id": "test-job-backend", "title": "Backend Developer"},
            ],
        )
    )
    assert scores[0].job_id == "test-job-mc"


def test_online_dqn_reward_updates_ranker(tmp_path: Path):
    agent = OnlineDQN(model_path=tmp_path / "online_dqn.json", load_existing=False)
    user_id = "test-online-dqn"
    mc = {"id": "test-dqn-mc", "title": "Master of Ceremony", "sbert_score": 0.8, "ncf_score": 0.7}
    backend = {"id": "test-dqn-backend", "title": "Backend Developer", "sbert_score": 0.2, "ncf_score": 0.2}
    before = agent.rank(user_id, [mc, backend], {"interaction_count": 0})

    for _ in range(15):
        agent.learn(RewardUpdateRequest(user_id=user_id, job_id=mc["id"], event="click", job=mc))
        agent.learn(RewardUpdateRequest(user_id=user_id, job_id=backend["id"], event="skip", job=backend, done=True))

    after = agent.rank(
        user_id,
        [mc, backend],
        {
            "interaction_count": 10,
            "interaction_history": [
                {"event": "click", "job_id": mc["id"]},
                {"event": "skip", "job_id": backend["id"]},
            ],
        },
    )

    assert after[0]["job"]["id"] == mc["id"]
    assert after[0]["dqn_session_score"] > before[0]["dqn_session_score"]


def test_aggregate_uses_learned_scores_without_static_domain_cap():
    user = {"id": "u-1", "program_studi": "Sastra Inggris", "interaction_count": 30}
    jobs = [
        {"id": "backend", "title": "Backend Developer", "sbert_score": 0.2, "ncf_score": 0.8, "dqn_score": 0.95},
        {"id": "mc", "title": "Master of Ceremony", "sbert_score": 0.8, "ncf_score": 0.3, "dqn_score": 0.2},
    ]

    result = asyncio.run(run_aggregate_stage(user, jobs))

    assert result.summary["strategy"] == "transparent_alpha_beta_gamma_hybrid_with_separate_calibration"
    assert result.summary["static_baseline"] == "static_weighted_hybrid"
    assert result.summary["calibrator"]["mode"] == "learned_logistic"
    assert result.ranked[0]["id"] == "backend"
    assert result.ranked[0]["final_score"] > 0.35
    assert result.ranked[0]["ablation_scores"]["static_baseline"] == result.ranked[0]["static_baseline_score"]
