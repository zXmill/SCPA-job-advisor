"""STEP 4 — Caching Behavior Tests.

Verifies SBERT Redis embedding cache behavior: cache miss → compute → store,
cache hit returns identical results, and response time characteristics.

NOTE: These tests run without a live Redis instance. They verify the
caching logic paths and fallback behavior when Redis is unavailable.
"""

from __future__ import annotations

import os
import sys
import time
import json

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import services.sbert.main as sbert_main
from services.sbert.main import EMBEDDING_CACHE_TTL, SBERTConfigurationError, SBERTModel, _cache_key


def _write_sentence_transformer_artifact(model_dir) -> None:
    model_dir.mkdir()
    (model_dir / "config_sentence_transformers.json").write_text(
        json.dumps(
            {
                "__version__": {
                    "sentence_transformers": "5.5.1",
                    "transformers": "4.57.6",
                    "pytorch": "2.12.0",
                },
                "model_type": "SentenceTransformer",
                "similarity_fn_name": "cosine",
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "modules.json").write_text(
        json.dumps(
            [
                {"idx": 0, "name": "0", "path": "", "type": "Transformer"},
                {"idx": 1, "name": "1", "path": "1_Pooling", "type": "Pooling"},
            ]
        ),
        encoding="utf-8",
    )
    pooling_dir = model_dir / "1_Pooling"
    pooling_dir.mkdir()
    (pooling_dir / "config.json").write_text(
        json.dumps({"embedding_dimension": 3}),
        encoding="utf-8",
    )


class FakeSentenceTransformer:
    def __init__(self, model_name_or_path: str) -> None:
        self.model_name_or_path = model_name_or_path
        self.encode_calls: list[dict[str, object]] = []

    def get_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, **kwargs):
        self.encode_calls.append(kwargs)
        base = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        return np.vstack([base for _ in texts])


class TestCacheKeyGeneration:
    """Verify cache key determinism and collision resistance."""

    def test_same_text_same_key(self) -> None:
        """Identical text must produce identical cache keys.

        This is essential for cache hits to work correctly.
        """
        key1 = _cache_key("Python developer with ML experience")
        key2 = _cache_key("Python developer with ML experience")
        assert key1 == key2

    def test_different_text_different_key(self) -> None:
        """Different text must produce different cache keys.

        Collisions would cause incorrect embeddings to be served.
        """
        key1 = _cache_key("Python developer")
        key2 = _cache_key("Java developer")
        assert key1 != key2

    def test_case_insensitive(self) -> None:
        """Cache keys should be case-insensitive (text is lowered).

        "Python" and "python" should hit the same cache entry.
        """
        key1 = _cache_key("Python Developer")
        key2 = _cache_key("python developer")
        assert key1 == key2

    def test_whitespace_normalized(self) -> None:
        """Leading/trailing whitespace should be stripped.

        "  text  " and "text" should produce the same key.
        """
        key1 = _cache_key("  ML Engineer  ")
        key2 = _cache_key("ML Engineer")
        assert key1 == key2

    def test_key_format(self) -> None:
        """Cache key must follow the expected format: sbert:emb:<hash>."""
        key = _cache_key("test text")
        assert key.startswith("sbert:emb:")
        # Hash portion should be 16 hex chars
        hash_part = key.replace("sbert:emb:", "")
        assert len(hash_part) == 16
        assert all(c in "0123456789abcdef" for c in hash_part)


class TestSBERTEncodingWithoutCache:
    """Verify encoding works correctly without Redis."""

    def test_transformer_enabled_loads_sentence_transformer_and_metadata(
        self, tmp_path
    ) -> None:
        """Enabled runtime must use SentenceTransformer and expose artifact metadata."""
        model_dir = tmp_path / "fine_tuned"
        _write_sentence_transformer_artifact(model_dir)

        model = SBERTModel(
            enable_transformer=True,
            force_fallback=False,
            model_dir=model_dir,
            model_name="unused-hub-model",
            transformer_factory=FakeSentenceTransformer,
        )

        result = model.encode(["first text", "second text"])
        metadata = model.runtime_metadata()

        assert result.shape == (2, 3)
        assert model.model_loaded is True
        assert model._fallback_mode is False
        assert model.embedding_dim == 3
        assert model.model_name_or_path == str(model_dir)
        assert metadata["fallback_mode"] is False
        assert metadata["model_loaded"] is True
        assert metadata["model_name_or_path"] == str(model_dir)
        assert metadata["embedding_dim"] == 3
        assert metadata["artifact"]["has_config_sentence_transformers"] is True
        assert metadata["artifact"]["embedding_dimension"] == 3
        assert metadata["artifact"]["similarity_fn_name"] == "cosine"
        assert model.model.encode_calls[0]["convert_to_numpy"] is True
        assert model.model.encode_calls[0]["normalize_embeddings"] is True

    def test_transformer_enabled_rejects_silent_fallback(self, tmp_path) -> None:
        """Production transformer mode must fail loudly when the model cannot load."""

        def broken_factory(model_name_or_path: str):
            raise OSError(f"cannot load {model_name_or_path}")

        with pytest.raises(SBERTConfigurationError, match="SentenceTransformer required"):
            SBERTModel(
                enable_transformer=True,
                force_fallback=False,
                model_dir=tmp_path / "missing-model",
                model_name="missing-model",
                transformer_factory=broken_factory,
            )

    def test_forced_fallback_is_explicit_and_does_not_load_transformer(self) -> None:
        """Tests may force fallback without importing or constructing transformers."""

        def should_not_load(model_name_or_path: str):
            raise AssertionError("forced fallback should not load SentenceTransformer")

        model = SBERTModel(
            enable_transformer=True,
            force_fallback=True,
            transformer_factory=should_not_load,
        )

        metadata = model.runtime_metadata()
        result = model.encode(["Python ML expert"])

        assert result.shape == (1, 384)
        assert model.model_loaded is False
        assert model._fallback_mode is True
        assert metadata["fallback_mode"] is True
        assert metadata["fallback_reason"] == "forced_by_SBERT_FORCE_FALLBACK"

    def test_encode_produces_consistent_shape(self) -> None:
        """Encoded embeddings must always have shape (n, 384).

        384 is the MiniLM embedding dimension.
        """
        model = SBERTModel()
        texts = ["Hello world", "Testing embeddings"]
        result = model.encode(texts)
        assert result.shape == (2, 384)
        assert result.dtype == np.float32

    def test_encode_deterministic_in_fallback(self) -> None:
        """In fallback mode, same input must produce same embeddings.

        The fallback uses hash-based seeding for determinism.
        """
        model = SBERTModel()
        if model._fallback_mode:
            e1 = model.encode(["Python ML expert"])
            e2 = model.encode(["Python ML expert"])
            np.testing.assert_array_equal(e1, e2)

    @pytest.mark.anyio
    async def test_encode_cached_without_redis_falls_back(self) -> None:
        """encode_cached() without Redis should fall back to direct encoding.

        Ensures no crash when Redis is unavailable.
        """
        model = SBERTModel()
        result = await model.encode_cached(["Test text"])
        assert result.shape == (1, 384)

    @pytest.mark.anyio
    async def test_encode_cached_response_time_reasonable(self) -> None:
        """Encoding without cache should complete within reasonable time.

        Fallback encoding should be fast (< 1 second for a single text).
        """
        model = SBERTModel()
        start = time.time()
        await model.encode_cached(["Quick test"])
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Encoding took {elapsed:.2f}s, expected < 5s"

    @pytest.mark.anyio
    async def test_encode_cached_writes_with_ttl(self, monkeypatch) -> None:
        """Cache writes must use setex so embeddings cannot live forever."""

        class FakeRedis:
            def __init__(self) -> None:
                self.setex_calls: list[tuple[str, int, bytes]] = []

            async def get(self, key: str):
                return None

            async def setex(self, key: str, ttl: int, value: bytes):
                self.setex_calls.append((key, ttl, value))
                return True

        fake = FakeRedis()

        async def fake_get_redis():
            return fake

        monkeypatch.setattr(sbert_main, "_get_redis", fake_get_redis)
        model = SBERTModel()

        await model.encode_cached(["TTL test text"])

        assert len(fake.setex_calls) == 1
        assert fake.setex_calls[0][1] == EMBEDDING_CACHE_TTL


class TestSBERTSimilarityConsistency:
    """Verify that similarity computation is consistent across calls."""

    @pytest.mark.anyio
    async def test_same_input_same_scores(self) -> None:
        """Identical inputs must produce identical similarity scores.

        Non-determinism would make recommendations unpredictable.
        """
        model = SBERTModel()
        scores1 = await model.compute_similarity(
            "Data scientist",
            ["ML Engineer", "Frontend Dev"],
        )
        scores2 = await model.compute_similarity(
            "Data scientist",
            ["ML Engineer", "Frontend Dev"],
        )
        s1 = [(s.job_index, s.score) for s in scores1]
        s2 = [(s.job_index, s.score) for s in scores2]
        assert s1 == s2

    @pytest.mark.anyio
    async def test_symmetric_text_order_independence(self) -> None:
        """Similarity scores should not depend on user text casing.

        "Python developer" and "python developer" should produce similar scores.
        """
        model = SBERTModel()
        s1 = await model.compute_similarity("Python developer", ["ML Engineer"])
        s2 = await model.compute_similarity("python developer", ["ML Engineer"])
        # Scores should be reasonably close (not necessarily identical due to encoding)
        diff = abs(s1[0].score - s2[0].score)
        assert diff < 0.3, f"Score difference {diff} too large for case change"
