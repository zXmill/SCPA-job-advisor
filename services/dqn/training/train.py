"""Bootstrap and validate the online DQN reranker."""

from __future__ import annotations

from services.dqn.main import OnlineDQN, RewardUpdateRequest, reward_value


def main() -> None:
    agent = OnlineDQN()
    positive_job = {"id": "job-mc", "title": "Master of Ceremony", "sbert_score": 0.8, "ncf_score": 0.7}
    negative_job = {"id": "job-backend", "title": "Backend Developer", "sbert_score": 0.1, "ncf_score": 0.2}
    agent.upsert_jobs([positive_job, negative_job])

    before = agent.rank("u-1", [positive_job, negative_job], {"interaction_count": 0})
    for _ in range(20):
        agent.learn(RewardUpdateRequest(user_id="u-1", job_id="job-mc", event="click", job=positive_job))
        agent.learn(RewardUpdateRequest(user_id="u-1", job_id="job-backend", event="skip", job=negative_job, done=True))
    after = agent.rank("u-1", [positive_job, negative_job], {"interaction_count": 10})

    assert reward_value("apply", same_domain=False) == 0.2
    assert after[0]["job"]["id"] == "job-mc"
    agent.soft_update()
    agent.save()
    print({"before": before, "after": after, "training_steps": agent.training_steps})


if __name__ == "__main__":
    main()
