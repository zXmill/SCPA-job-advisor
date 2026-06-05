"""SCPA SBERT service.

Production mode REQUIRES a real SentenceTransformer model.
Deterministic lexical fallback is available ONLY when explicitly enabled
via ``SBERT_FORCE_FALLBACK=1`` (test mode). If the model cannot be loaded
and fallback is not forced, the service raises ``SBERTConfigurationError``
on startup.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, List

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:  # Supports both repo imports and the service Docker image's /app layout.
    from services.sbert.weights.validation import validate_sbert_artifact
except ImportError:  # pragma: no cover - exercised only in the service image
    from weights.validation import validate_sbert_artifact

app = FastAPI(
    title="SCPA SBERT Service",
    description="Profile-to-job semantic matching with lightweight fallback scoring",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = os.environ.get(
    "MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
_TRUE_VALUES = {"1", "true", "yes", "on"}
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_FINETUNED_MODEL_DIR = _PROJECT_ROOT / "models" / "sbert-indonesian-hybrid-manual-research" / "best"
_LEGACY_MODEL_DIR = Path(__file__).resolve().parent / "weights" / "fine_tuned_jupyter"
_LOCAL_MODEL_DIR = _FINETUNED_MODEL_DIR if _FINETUNED_MODEL_DIR.exists() else _LEGACY_MODEL_DIR
_CONTAINER_MODEL_DIR = Path("/app/weights/sbert")
DEFAULT_MODEL_LOADER = os.environ.get("SBERT_MODEL_LOADER", "transformers")
MAX_SEQ_LENGTH = int(os.environ.get("SBERT_MAX_SEQ_LENGTH", "256"))
ENCODE_BATCH_SIZE = int(os.environ.get("SBERT_ENCODE_BATCH_SIZE", "32"))


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


MODEL_DIR = os.environ.get(
    "MODEL_DIR",
    str(_LOCAL_MODEL_DIR if _LOCAL_MODEL_DIR.exists() else _CONTAINER_MODEL_DIR),
)
ENABLE_TRANSFORMER = _env_flag("SBERT_ENABLE_TRANSFORMER", default=True)
FORCE_FALLBACK = _env_flag("SBERT_FORCE_FALLBACK")
REDIS_URL = os.environ.get("REDIS_URL", "")
EMBEDDING_CACHE_TTL = int(os.environ.get("EMBEDDING_CACHE_TTL", "3600"))

EMBEDDING_DIM = 384
_redis_client = None
_transformer_cache: dict[str, Any] = {}
_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")

_ALIASES: dict[str, set[str]] = {
    "communication": {
        "communication",
        "communicator",
        "presenter",
        "presentation",
        "public",
        "speaking",
        "speaker",
        "host",
        "hosting",
        "mc",
        "master",
        "ceremony",
        "emcee",
        "announcer",
        "moderator",
    },
    "language": {
        "english",
        "inggris",
        "sastra",
        "literature",
        "translator",
        "translation",
        "writing",
        "copywriting",
        "content",
    },
    "event": {
        "event",
        "ceremony",
        "wedding",
        "seminar",
        "conference",
        "workshop",
        "protocol",
        "audience",
    },
    "software": {
        "backend",
        "frontend",
        "developer",
        "engineer",
        "python",
        "java",
        "javascript",
        "fastapi",
        "django",
        "api",
        "database",
        "postgres",
        "react",
        "node",
        "server",
        "microservice",
    },
    "data": {
        "data",
        "machine",
        "learning",
        "ml",
        "ai",
        "analytics",
        "scientist",
        "pandas",
        "numpy",
        "model",
    },
    "business": {
        "sales",
        "marketing",
        "business",
        "account",
        "customer",
        "relationship",
        "growth",
    },
    "design": {
        "ui",
        "ux",
        "designer",
        "figma",
        "prototype",
        "visual",
        "product",
    },
}

_INDONESIAN_NORMALISATION = {
    "bahasa": "language",
    "inggris": "english",
    "pembawa": "host",
    "acara": "event",
    "pewara": "emcee",
    "komunikasi": "communication",
}


class SBERTRequest(BaseModel):
    user_profile_text: str
    job_descriptions: List[str]


class EncodeRequest(BaseModel):
    texts: List[str]


class EncodeResponse(BaseModel):
    embeddings: List[List[float]]
    embedding_dim: int
    model_name: str
    model_version: str
    fallback_mode: bool


class SimilarityScore(BaseModel):
    job_index: int
    score: float
    job_text_preview: str


class SBERTResponse(BaseModel):
    scores: List[SimilarityScore]
    model_version: str = "sbert-v1.0"
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"


async def _get_redis():
    """Lazy optional Redis client used only when REDIS_URL is configured."""
    global _redis_client
    if _redis_client is None and REDIS_URL:
        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(REDIS_URL, decode_responses=False)
        except Exception as exc:  # pragma: no cover - depends on local service
            logger.warning("Redis cache disabled: %s", exc)
            _redis_client = False
    return _redis_client if _redis_client is not False else None


def _cache_key(text: str) -> str:
    text_hash = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"sbert:emb:{text_hash}"


class SBERTConfigurationError(RuntimeError):
    """Raised when production transformer mode cannot load a valid model."""


def _resolve_model_name_or_path(
    model_dir: str,
    model_name: str,
    *,
    model_dir_configured: bool,
) -> tuple[str, str | None]:
    if model_dir:
        path = Path(model_dir)
        if path.exists():
            files = [entry for entry in path.iterdir()]
            if not files:
                if model_dir_configured:
                    raise SBERTConfigurationError(
                        f"Configured MODEL_DIR '{path}' is empty; expected a SentenceTransformer artifact."
                    )
                return model_name, None

            config_path = path / "config_sentence_transformers.json"
            if not config_path.exists():
                raise SBERTConfigurationError(
                    f"MODEL_DIR '{path}' is missing config_sentence_transformers.json; "
                    "refusing silent fallback in transformer mode."
                )
            return str(path), str(config_path)

        if model_dir_configured:
            raise SBERTConfigurationError(
                f"Configured MODEL_DIR '{path}' does not exist; expected a SentenceTransformer artifact."
            )

    return model_name, None


def _model_embedding_dim(model: Any) -> int:
    get_dim = getattr(model, "get_embedding_dimension", None)
    if callable(get_dim):
        dimension = get_dim()
        if dimension:
            return int(dimension)

    get_legacy_dim = getattr(model, "get_sentence_embedding_dimension", None)
    if callable(get_legacy_dim):
        dimension = get_legacy_dim()
        if dimension:
            return int(dimension)

    return EMBEDDING_DIM


class TransformersSentenceEncoder:
    """SentenceTransformer-compatible inference wrapper using transformers only."""

    def __init__(
        self,
        model_name_or_path: str,
        *,
        max_seq_length: int = MAX_SEQ_LENGTH,
        batch_size: int = ENCODE_BATCH_SIZE,
    ) -> None:
        import torch
        import torch.nn.functional as functional
        from transformers import AutoModel, AutoTokenizer

        self.model_name_or_path = str(model_name_or_path)
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size
        self._torch = torch
        self._functional = functional
        requested_device = os.environ.get("SBERT_DEVICE", "cpu")
        if requested_device.startswith("cuda") and not torch.cuda.is_available():
            requested_device = "cpu"
        self.device = torch.device(requested_device)
        local_files_only = Path(self.model_name_or_path).exists()
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path,
            local_files_only=local_files_only,
        )
        self.model = AutoModel.from_pretrained(
            self.model_name_or_path,
            local_files_only=local_files_only,
        )
        self.model.to(self.device)
        self.model.eval()
        self.embedding_dim = int(getattr(self.model.config, "hidden_size", EMBEDDING_DIM))

    def get_embedding_dimension(self) -> int:
        return self.embedding_dim

    def get_sentence_embedding_dimension(self) -> int:
        return self.embedding_dim

    def encode(
        self,
        texts: List[str],
        *,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
        batch_size: int | None = None,
    ) -> np.ndarray:
        del show_progress_bar
        if isinstance(texts, str):
            texts = [texts]
        torch = self._torch
        functional = self._functional
        effective_batch_size = batch_size or self.batch_size
        chunks: list[Any] = []
        with torch.no_grad():
            for start in range(0, len(texts), effective_batch_size):
                batch_texts = texts[start : start + effective_batch_size]
                inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_seq_length,
                    return_tensors="pt",
                )
                inputs = {
                    key: value.to(self.device)
                    for key, value in inputs.items()
                    if hasattr(value, "to")
                }
                outputs = self.model(**inputs)
                token_embeddings = outputs.last_hidden_state
                attention_mask = inputs["attention_mask"].unsqueeze(-1)
                attention_mask = attention_mask.expand(token_embeddings.size()).float()
                pooled = (token_embeddings * attention_mask).sum(dim=1)
                pooled = pooled / torch.clamp(attention_mask.sum(dim=1), min=1e-9)
                if normalize_embeddings:
                    pooled = functional.normalize(pooled, p=2, dim=1)
                chunks.append(pooled.cpu())
        if not chunks:
            array = np.empty((0, self.embedding_dim), dtype=np.float32)
        else:
            array = torch.cat(chunks, dim=0).numpy().astype(np.float32)
        return array if convert_to_numpy else array


def _loader_backend() -> str:
    return os.environ.get("SBERT_MODEL_LOADER", DEFAULT_MODEL_LOADER).strip().lower()


def _load_sentence_transformer(model_name_or_path: str) -> Any:
    backend = _loader_backend()
    cache_key = f"{backend}:{model_name_or_path}"
    if cache_key not in _transformer_cache:
        if backend in {"sentence_transformer", "sentence-transformer", "sentence_transformers"}:
            from sentence_transformers import SentenceTransformer

            _transformer_cache[cache_key] = SentenceTransformer(model_name_or_path)
        elif backend in {"transformers", "auto"}:
            _transformer_cache[cache_key] = TransformersSentenceEncoder(model_name_or_path)
        else:
            raise SBERTConfigurationError(
                "SBERT_MODEL_LOADER must be 'transformers' or 'sentence_transformers'."
            )
    return _transformer_cache[cache_key]


def _tokens(text: str) -> list[str]:
    raw = _TOKEN_RE.findall(text.lower())
    return [_INDONESIAN_NORMALISATION.get(token, token) for token in raw]


def _category_scores(tokens: Iterable[str]) -> dict[str, float]:
    token_set = set(tokens)
    scores: dict[str, float] = {}
    for name, aliases in _ALIASES.items():
        overlap = token_set & aliases
        scores[name] = min(1.0, len(overlap) / 3.0)
    return scores


def _stable_noise(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    idx = 32 + int.from_bytes(digest[:2], "big") % (dim - 32)
    sign = 1.0 if digest[2] % 2 == 0 else -1.0
    return idx, sign * (0.08 + digest[3] / 2550.0)


def deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Create a normalized deterministic embedding without external weights."""
    tokens = _tokens(text)
    vec = np.zeros(dim, dtype=np.float32)
    categories = _category_scores(tokens)
    for idx, name in enumerate(_ALIASES):
        vec[idx] = categories[name]

    token_set = set(tokens)
    for token in token_set:
        idx, value = _stable_noise(token, dim)
        vec[idx] += value

    if not token_set:
        vec[31] = 1.0

    norm = np.linalg.norm(vec)
    if norm == 0:
        vec[31] = 1.0
        norm = 1.0
    return (vec / norm).astype(np.float32)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denom)


def sbert_score(user_profile_text: str, job_description: str) -> float:
    """Deterministic semantic score in [0, 1] for tests and offline demos."""
    left_tokens = set(_tokens(user_profile_text))
    right_tokens = set(_tokens(job_description))
    if not left_tokens or not right_tokens:
        return 0.2

    left_categories = _category_scores(left_tokens)
    right_categories = _category_scores(right_tokens)
    weighted_overlap = 0.0
    weighted_total = 0.0
    for name in _ALIASES:
        weight = 1.35 if name in {"communication", "language", "event", "software"} else 1.0
        weighted_overlap += weight * min(left_categories[name], right_categories[name])
        weighted_total += weight * max(left_categories[name], right_categories[name])

    category_score = weighted_overlap / weighted_total if weighted_total else 0.0
    lexical_score = len(left_tokens & right_tokens) / math.sqrt(
        max(1, len(left_tokens)) * max(1, len(right_tokens))
    )
    embedding_score = (_cosine(deterministic_embedding(user_profile_text), deterministic_embedding(job_description)) + 1.0) / 2.0

    score = 0.12 + 0.62 * category_score + 0.16 * lexical_score + 0.10 * embedding_score

    if left_categories["software"] and right_categories["software"]:
        score += 0.08
    if (
        (left_categories["communication"] or left_categories["language"])
        and (right_categories["communication"] or right_categories["event"])
        and not right_categories["software"]
    ):
        score += 0.24
    if (
        (left_categories["communication"] or left_categories["language"])
        and right_categories["software"]
        and not (left_categories["software"] or right_categories["communication"])
    ):
        score -= 0.18

    return round(float(min(1.0, max(0.0, score))), 4)


class SBERTModel:
    """Semantic encoder with optional SentenceTransformer and fast fallback."""

    def __init__(
        self,
        *,
        enable_transformer: bool | None = None,
        force_fallback: bool | None = None,
        model_dir: str | None = None,
        model_name: str | None = None,
        transformer_factory: Any | None = None,
    ) -> None:
        self.model = None
        self.model_loaded = False
        self.embedding_dim = EMBEDDING_DIM
        self.model_name = model_name if model_name is not None else os.environ.get("MODEL_NAME", MODEL_NAME)
        self.model_dir = model_dir if model_dir is not None else os.environ.get("MODEL_DIR", MODEL_DIR)
        self.force_fallback = (
            _env_flag("SBERT_FORCE_FALLBACK")
            if force_fallback is None
            else force_fallback
        )
        self.enable_transformer = (
            _env_flag("SBERT_ENABLE_TRANSFORMER", default=True)
            if enable_transformer is None
            else enable_transformer
        )
        self.transformer_required = self.enable_transformer and not self.force_fallback
        self._fallback_mode = False
        self.fallback_reason: str | None = None
        self.model_name_or_path = self.model_name
        self.model_artifact_config: str | None = None
        self.transformer_factory = transformer_factory or _load_sentence_transformer
        self.loader_backend = "custom" if transformer_factory else _loader_backend()
        self.model_version = "sbert-v1.0"
        self.artifact_metadata: dict[str, Any] = {
            "path": None,
            "artifact_name": None,
            "fine_tuned": False,
            "has_config_sentence_transformers": False,
            "embedding_dimension": None,
            "similarity_fn_name": None,
            "valid": False,
            "errors": [],
        }
        self.startup_error: str | None = None

        if self.force_fallback:
            self._fallback_mode = True
            self.fallback_reason = "forced_by_SBERT_FORCE_FALLBACK"
            self.model_name_or_path = "deterministic-fallback"
            self.model_version = "deterministic-fallback"
            logger.info("SBERT deterministic fallback enabled by SBERT_FORCE_FALLBACK")
            return

        if not self.enable_transformer:
            self.startup_error = (
                "SBERT transformer mode is disabled. Production mode requires a real "
                "SentenceTransformer model. Set SBERT_FORCE_FALLBACK=1 for explicit test mode."
            )
            logger.error(self.startup_error)
            if not self.force_fallback:
                raise SBERTConfigurationError(self.startup_error)
            return

        model_dir_configured = model_dir is not None or "MODEL_DIR" in os.environ
        try:
            self.model_name_or_path, self.model_artifact_config = _resolve_model_name_or_path(
                self.model_dir,
                self.model_name,
                model_dir_configured=model_dir_configured,
            )
            if self.model_artifact_config:
                self.artifact_metadata = self._artifact_metadata(self.model_name_or_path)
            self.model = self.transformer_factory(self.model_name_or_path)
            self.embedding_dim = _model_embedding_dim(self.model)
            if self.model_artifact_config:
                self.artifact_metadata = self._artifact_metadata(self.model_name_or_path)
                self.model_version = (
                    self.artifact_metadata.get("artifact_name")
                    or Path(self.model_name_or_path).name
                )
            else:
                self.model_version = self.model_name_or_path
            self.model_loaded = True
            logger.info("Loaded SentenceTransformer: %s", self.model_name_or_path)
        except Exception as exc:  # pragma: no cover - exact local model state varies
            self.startup_error = (
                f"SentenceTransformer required but unavailable for "
                f"'{self.model_dir or self.model_name}': {exc}"
            )
            logger.error(self.startup_error)
            raise SBERTConfigurationError(self.startup_error) from exc

    @staticmethod
    def _artifact_metadata(model_name_or_path: str | Path) -> dict[str, Any]:
        validation = validate_sbert_artifact(
            Path(model_name_or_path),
            require_metadata=False,
            require_reload=False,
        )
        payload = validation.as_dict()
        return {
            "path": payload["artifact_path"],
            "artifact_name": payload["artifact_name"],
            "fine_tuned": payload["fine_tuned"],
            "base_model": payload["base_model"],
            "has_config_sentence_transformers": payload[
                "config_sentence_transformers"
            ],
            "config_sentence_transformers": payload["config_sentence_transformers"],
            "metadata_file": payload["metadata_file"],
            "embedding_dimension": payload["embedding_dim"],
            "similarity_fn_name": payload["similarity_fn_name"],
            "valid": payload["valid"],
            "fallback_mode": payload["fallback_mode"],
            "fallback_reason": payload["fallback_reason"],
            "errors": payload["errors"],
        }

    def health_payload(self) -> dict[str, Any]:
        healthy = self._fallback_mode or (
            self.model_loaded
            and (not self.transformer_required or not self._fallback_mode)
        )
        payload: dict[str, Any] = {
            "status": "healthy" if healthy else "unhealthy",
            "service": "sbert",
            "model_loaded": self.model_loaded and not self._fallback_mode,
            "fallback_mode": self._fallback_mode,
            "fallback_reason": self.fallback_reason,
            "loader_backend": self.loader_backend,
            "model_version": self.model_version,
            "model_name_or_path": self.model_name_or_path,
            "embedding_dim": self.embedding_dim,
            "transformer_required": self.transformer_required,
            "test_fallback_enabled": self.force_fallback,
            "runtime_mode": "deterministic-fallback-test"
            if self._fallback_mode
            else "sentence-transformer",
            "model_artifact_config": self.model_artifact_config,
            "artifact": self.artifact_metadata,
        }
        if self.startup_error:
            payload["error"] = self.startup_error
        return payload

    def runtime_metadata(self) -> dict[str, Any]:
        return self.health_payload()

    def _ensure_ready(self) -> None:
        if self.model is not None or self._fallback_mode:
            return
        raise RuntimeError(
            self.startup_error
            or "SBERT model is unavailable and deterministic fallback is disabled."
        )

    def encode(self, texts: List[str]) -> np.ndarray:
        self._ensure_ready()
        if self.model is not None:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.astype(np.float32)
        return np.vstack([deterministic_embedding(text) for text in texts]).astype(np.float32)

    async def encode_cached(self, texts: List[str]) -> np.ndarray:
        self._ensure_ready()
        redis = await _get_redis()
        if redis is None:
            return self.encode(texts)

        results = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []
        for index, text in enumerate(texts):
            key = _cache_key(text)
            try:
                cached = await redis.get(key)
                if cached is not None:
                    results[index] = np.frombuffer(cached, dtype=np.float32)
                    continue
            except Exception as exc:
                logger.debug("Embedding cache read failed: %s", exc)
            uncached_indices.append(index)
            uncached_texts.append(text)

        if uncached_texts:
            embeddings = self.encode(uncached_texts)
            for offset, index in enumerate(uncached_indices):
                results[index] = embeddings[offset]
                try:
                    await redis.setex(
                        _cache_key(uncached_texts[offset]),
                        EMBEDDING_CACHE_TTL,
                        embeddings[offset].tobytes(),
                    )
                except Exception as exc:
                    logger.debug("Embedding cache write failed: %s", exc)
        return results

    async def compute_similarity(
        self,
        user_profile_text: str,
        job_descriptions: List[str],
    ) -> List[SimilarityScore]:
        self._ensure_ready()
        if self.model is not None:
            user_embedding = await self.encode_cached([user_profile_text])
            job_embeddings = await self.encode_cached(job_descriptions)
            raw_scores = np.dot(job_embeddings, user_embedding[0])
            scores = [round(float((score + 1.0) / 2.0), 4) for score in raw_scores]
        else:
            scores = [
                sbert_score(user_profile_text, description)
                for description in job_descriptions
            ]

        results = [
            SimilarityScore(
                job_index=index,
                score=float(score),
                job_text_preview=description[:100] + "..." if len(description) > 100 else description,
            )
            for index, (description, score) in enumerate(zip(job_descriptions, scores))
        ]
        results.sort(key=lambda item: item.score, reverse=True)
        return results


sbert_model = SBERTModel()


@app.get("/health")
async def health_check():
    payload = sbert_model.health_payload()
    if payload["status"] != "healthy":
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.post("/match/semantic", response_model=SBERTResponse)
async def match_semantic(request: SBERTRequest):
    if not request.user_profile_text or not request.user_profile_text.strip():
        raise HTTPException(status_code=400, detail="user_profile_text cannot be empty")
    if not request.job_descriptions:
        raise HTTPException(status_code=400, detail="job_descriptions cannot be empty")
    for jd in request.job_descriptions:
        if not jd or not jd.strip():
            raise HTTPException(status_code=400, detail="job_descriptions cannot contain empty strings")
    try:
        scores = await sbert_model.compute_similarity(
            request.user_profile_text,
            request.job_descriptions,
        )
        return SBERTResponse(
            scores=scores,
            model_version=sbert_model.model_version,
            model_name=sbert_model.model_name_or_path,
        )
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SBERT matching error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/encode", response_model=EncodeResponse)
async def encode_texts(request: EncodeRequest):
    if not request.texts:
        raise HTTPException(status_code=400, detail="texts cannot be empty")
    for text in request.texts:
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="texts cannot contain empty strings")
    try:
        embeddings = await sbert_model.encode_cached(request.texts)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EncodeResponse(
        embeddings=embeddings.tolist(),
        embedding_dim=sbert_model.embedding_dim,
        model_name=sbert_model.model_name_or_path,
        model_version=sbert_model.model_version,
        fallback_mode=sbert_model._fallback_mode,
    )


@app.get("/metrics")
async def get_metrics():
    return {
        "service": "sbert",
        "metrics": {
            "embedding_dim": sbert_model.embedding_dim,
            "model": sbert_model.model_name_or_path,
            "model_version": sbert_model.model_version,
            "loader_backend": sbert_model.loader_backend,
            "fallback_mode": sbert_model._fallback_mode,
            "cache_ttl_seconds": EMBEDDING_CACHE_TTL,
            "latency_mode": "deterministic-fallback"
            if sbert_model._fallback_mode
            else "sentence-transformer",
        },
    }
