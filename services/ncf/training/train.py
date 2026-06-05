"""Bootstrap and validate the online NCF model.

This entrypoint performs real SGD updates on implicit feedback events and writes
the persisted model artifact used by the service.
"""

from __future__ import annotations

from services.ncf.main import FeedbackEvent, MODEL_PATH, OnlineNCF


def main() -> None:
    model = OnlineNCF()
    candidates = ["job-mc", "job-translator", "job-content", "job-backend", "job-software"]
    before = [model.predict_one("u-1", job, profile_text="Sastra Inggris Public Speaking") for job in candidates]

    events = [
        FeedbackEvent(user_id="u-1", job_id="job-mc", event="click", profile_text="Sastra Inggris Public Speaking"),
        FeedbackEvent(user_id="u-1", job_id="job-translator", event="apply", profile_text="Sastra Inggris Public Speaking"),
        FeedbackEvent(user_id="u-1", job_id="job-backend", event="skip", profile_text="Sastra Inggris Public Speaking"),
    ]
    for _ in range(25):
        for event in events:
            target = 1.0 if event.event in {"click", "apply"} else 0.0
            model.learn_one(str(event.user_id), event.job_id, target, event.profile_text)

    after = [model.predict_one("u-1", job, profile_text="Sastra Inggris Public Speaking") for job in candidates]
    assert len(set(round(score, 3) for score in after)) > 1, "NCF scores must be non-constant"
    assert after[candidates.index("job-mc")] > after[candidates.index("job-backend")]
    model.save()
    print({"before": before, "after": after, "artifact": str(MODEL_PATH)})


if __name__ == "__main__":
    main()
