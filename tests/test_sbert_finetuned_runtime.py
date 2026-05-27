"""Fine-tuned SBERT runtime integration tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from services.sbert.main import SBERTModel
from services.sbert.weights.validation import validate_sbert_artifact


FINETUNED_SBERT_DIR = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "sbert-indonesian-hybrid-manual-research"
    / "best"
)


def _require_finetuned_artifact() -> Path:
    if not FINETUNED_SBERT_DIR.exists():
        pytest.skip("fine-tuned SBERT checkpoint is not present in this checkout")
    return FINETUNED_SBERT_DIR


def test_finetuned_sbert_artifact_metadata_is_valid() -> None:
    model_dir = _require_finetuned_artifact()

    result = validate_sbert_artifact(
        model_dir,
        expected_embedding_dim=384,
        require_metadata=True,
        require_reload=False,
    )
    payload = result.as_dict()

    assert result.valid is True
    assert payload["artifact_name"] == "sbert-indonesian-hybrid-manual-research-best"
    assert payload["fine_tuned"] is True
    assert payload["embedding_dim"] == 384
    assert payload["similarity_fn_name"] == "cosine"


def test_sbert_service_loads_finetuned_checkpoint_without_fallback(monkeypatch) -> None:
    model_dir = _require_finetuned_artifact()
    monkeypatch.delenv("SBERT_FORCE_FALLBACK", raising=False)
    monkeypatch.setenv("SBERT_MODEL_LOADER", "transformers")
    monkeypatch.setenv("SBERT_MAX_SEQ_LENGTH", "256")

    model = SBERTModel(
        enable_transformer=True,
        force_fallback=False,
        model_dir=model_dir,
        model_name="unused-base-model",
    )

    embeddings = model.encode(
        [
            "Mahasiswa Sastra Inggris dengan public speaking dan pembawa acara.",
            "Backend developer Python FastAPI PostgreSQL untuk API produksi.",
        ]
    )
    metadata = model.runtime_metadata()

    assert embeddings.shape == (2, 384)
    np.testing.assert_allclose(np.linalg.norm(embeddings, axis=1), [1.0, 1.0], rtol=1e-4)
    assert model.model_loaded is True
    assert model._fallback_mode is False
    assert metadata["loader_backend"] == "transformers"
    assert metadata["model_version"] == "sbert-indonesian-hybrid-manual-research-best"
    assert metadata["artifact"]["fine_tuned"] is True
    assert metadata["artifact"]["valid"] is True
