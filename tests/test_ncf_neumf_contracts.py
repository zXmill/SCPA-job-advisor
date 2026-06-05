"""Contracts for NCF NeuMF serving, mappings, and checkpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from services.ncf.main import CandidateJob, NCFRequest, NeuralCF, OnlineNCF


def test_neuralcf_exposes_gmf_mlp_fusion_forward() -> None:
    model = NeuralCF(num_users=3, num_items=4, embedding_dim=8, hidden_dim=16)

    logits = model(
        torch.tensor([0, 1, 2], dtype=torch.long),
        torch.tensor([1, 2, 3], dtype=torch.long),
    )

    assert logits.shape == (3,)
    assert model.user_gmf.num_embeddings == 3
    assert model.item_gmf.num_embeddings == 4
    assert model.user_mlp.num_embeddings == 3
    assert model.item_mlp.num_embeddings == 4
    assert model.out.in_features == 16


def test_online_ncf_persists_stable_mappings_and_neumf_checkpoint(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "online_ncf.json"
    model = OnlineNCF(model_path=model_path, load_existing=False)
    user_id = "user-neumf"
    profile = "Python backend FastAPI PostgreSQL"

    before_positive = model.predict_one(
        user_id,
        "job-backend",
        profile_text=profile,
        job_embedding=[0.9, 0.8, 0.7, 0.6],
    )
    before_negative = model.predict_one(
        user_id,
        "job-unrelated",
        profile_text=profile,
        job_embedding=[-0.5, -0.4, -0.3, -0.2],
    )

    for _ in range(20):
        model.learn_one(
            user_id,
            "job-backend",
            1.0,
            profile_text=profile,
            job_embedding=[0.9, 0.8, 0.7, 0.6],
        )
        model.learn_one(
            user_id,
            "job-unrelated",
            0.0,
            profile_text=profile,
            job_embedding=[-0.5, -0.4, -0.3, -0.2],
        )

    after_positive = model.predict_one(user_id, "job-backend", profile_text=profile)
    after_negative = model.predict_one(user_id, "job-unrelated", profile_text=profile)
    model.save()

    payload = json.loads(model_path.read_text(encoding="utf-8"))
    assert payload["architecture"] == "NeuMF(GMF+MLP)-online"
    assert payload["user_index"][user_id] == 0
    assert payload["item_index"] == {"job-backend": 0, "job-unrelated": 1}
    assert model.neumf_checkpoint_path.exists()
    assert after_positive > before_positive
    assert after_negative < before_negative

    reloaded = OnlineNCF(model_path=model_path, load_existing=True)
    assert reloaded.user_index == model.user_index
    assert reloaded.item_index == model.item_index
    assert reloaded.neumf_model is not None
    assert reloaded.predict_one(user_id, "job-backend", profile_text=profile) == pytest.approx(
        after_positive,
        abs=1e-6,
    )


def test_online_ncf_recommend_does_not_autosave_candidate_upserts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = OnlineNCF(model_path=tmp_path / "online_ncf.json", load_existing=False)
    save_calls = 0

    def counted_save() -> None:
        nonlocal save_calls
        save_calls += 1

    monkeypatch.setattr(model, "save", counted_save)

    model.recommend(
        NCFRequest(
            user_id="latency-user",
            n_items=2,
            candidates=[
                CandidateJob(id="job-1", title="Backend"),
                CandidateJob(id="job-2", title="Data"),
            ],
        ),
    )

    assert save_calls == 0


def test_online_ncf_recommend_calls_neumf_forward_when_torch_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract test: recommend() must invoke the neural model, not fall back to MF."""
    model = OnlineNCF(model_path=tmp_path / "online_ncf.json", load_existing=False)
    if model.neumf_model is None:
        pytest.skip("torch unavailable — neural path not testable")

    # Pre-warm indices so _ensure_neumf_capacity does not replace the model
    # mid-test and invalidate our forward monkeypatch.
    model._ensure_user_index("neural-user")
    model._ensure_item_index("job-1")
    model._ensure_item_index("job-2")

    forward_calls = 0
    original_forward = model.neumf_model.forward

    def counted_forward(user_ids, item_ids):
        nonlocal forward_calls
        forward_calls += 1
        return original_forward(user_ids, item_ids)

    monkeypatch.setattr(model.neumf_model, "forward", counted_forward)
    # Freeze capacity so recommend() cannot swap out the model object.
    monkeypatch.setattr(model, "_ensure_neumf_capacity", lambda: None)

    model.recommend(
        NCFRequest(
            user_id="neural-user",
            n_items=2,
            candidates=[
                CandidateJob(id="job-1", title="Backend"),
                CandidateJob(id="job-2", title="Data"),
            ],
        ),
    )

    assert forward_calls == 1, "recommend() must batch all candidates into one NeuMF forward call"
