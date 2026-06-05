"""Online NeuMF service for real-time job recommendation.

The active scorer is a neural collaborative filtering model (GMF + MLP), while
the matrix-factorization implementation is retained as an explicit baseline.
"""

from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

try:
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - torch is present in the target env
    torch = None
    nn = None


MODEL_VERSION = "online-ncf-v2"
FACTOR_DIM = int(os.getenv("NCF_FACTOR_DIM", "64"))
LEARNING_RATE = float(os.getenv("NCF_LEARNING_RATE", "0.045"))
REGULARIZATION = float(os.getenv("NCF_REGULARIZATION", "0.0005"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(Path(__file__).resolve().parent / "weights")))
MODEL_PATH = MODEL_DIR / "online_ncf.json"


EVENT_TARGETS = {
    "apply": 1.0,
    "click": 1.0,
    "save": 0.85,
    "view_10s": 0.65,
    "long_view": 0.65,
    "view": 0.45,
    "impression": 0.20,
    "skip": 0.0,
    "immediate_skip": 0.0,
    "skip_immediately": 0.0,
}


if nn is not None:
    class NeuralCF(nn.Module):
        """GMF + MLP Neural Collaborative Filtering checkpoint model."""

        def __init__(
            self,
            num_users: int,
            num_items: int,
            embedding_dim: int = 64,
            hidden_dim: int = 128,
        ) -> None:
            super().__init__()
            self.user_gmf = nn.Embedding(num_users, embedding_dim)
            self.item_gmf = nn.Embedding(num_items, embedding_dim)
            self.user_mlp = nn.Embedding(num_users, embedding_dim)
            self.item_mlp = nn.Embedding(num_items, embedding_dim)
            self.mlp = nn.Sequential(
                nn.Linear(embedding_dim * 2, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
            )
            self.out = nn.Linear(embedding_dim + hidden_dim // 2, 1)

        def forward(self, user_ids, item_ids):
            gmf = self.user_gmf(user_ids) * self.item_gmf(item_ids)
            mlp = self.mlp(torch.cat([self.user_mlp(user_ids), self.item_mlp(item_ids)], dim=-1))
            return self.out(torch.cat([gmf, mlp], dim=-1)).squeeze(-1)
else:
    class NeuralCF:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyTorch is required for NeuralCF")


class CandidateJob(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    sbert_score: float = 0.0


class NCFRequest(BaseModel):
    user_id: int | str
    n_items: int = Field(default=10, ge=0, le=10_000)
    profile_text: str | None = None
    interaction_count: int = Field(default=0, ge=0)
    user_embedding: list[float] | None = None
    candidate_job_ids: list[str] | None = None
    candidates: list[CandidateJob] | None = None


class NCFScore(BaseModel):
    job_id: str
    score: float
    mf_score: float | None = None
    pop_score: int | None = None


class NCFResponse(BaseModel):
    user_id: str
    recommendations: list[NCFScore]
    model_version: str = MODEL_VERSION


class FeedbackEvent(BaseModel):
    user_id: int | str
    job_id: str
    event: str = "view"
    value: float | None = None
    profile_text: str | None = None
    user_embedding: list[float] | None = None
    job_embedding: list[float] | None = None


class JobUpsertRequest(BaseModel):
    jobs: list[CandidateJob]


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


def _seeded_vector(seed: str, dim: int = FACTOR_DIM) -> np.ndarray:
    import hashlib

    digest = hashlib.blake2b(seed.encode("utf-8", "ignore"), digest_size=64).digest()
    raw = np.frombuffer(digest, dtype=np.uint8).astype(np.float32)
    values = np.tile(raw, math.ceil(dim / raw.size))[:dim]
    values = (values / 127.5) - 1.0
    norm = float(np.linalg.norm(values))
    return values / norm if norm else values


def _project_embedding(values: list[float] | None, seed: str, dim: int = FACTOR_DIM) -> np.ndarray:
    if not values:
        return _seeded_vector(seed, dim)
    arr = np.asarray(values, dtype=np.float32)
    if arr.size == 0:
        return _seeded_vector(seed, dim)
    if arr.size < dim:
        arr = np.tile(arr, math.ceil(dim / arr.size))[:dim]
    else:
        chunks = np.array_split(arr, dim)
        arr = np.asarray([float(chunk.mean()) for chunk in chunks], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else _seeded_vector(seed, dim)


class OnlineMF:
    """Online matrix factorization baseline."""

    def __init__(
        self,
        dim: int = FACTOR_DIM,
        lr: float = LEARNING_RATE,
        reg: float = REGULARIZATION,
        *,
        model_path: Path | None = None,
        autosave: bool = True,
        load_existing: bool = True,
    ) -> None:
        self.dim = dim
        self.lr = lr
        self.reg = reg
        self.model_path = model_path or MODEL_PATH
        self.autosave = autosave
        self.user_factors: dict[str, np.ndarray] = {}
        self.item_factors: dict[str, np.ndarray] = {}
        self.user_index: dict[str, int] = {}
        self.item_index: dict[str, int] = {}
        self.user_bias: dict[str, float] = {}
        self.item_bias: dict[str, float] = {}
        self.job_meta: dict[str, Any] = {}
        self.global_bias = 0.0
        self.feedback_events = 0
        self.job_upserts = 0
        self.last_trained_at: float | None = None
        if load_existing:
            self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            return
        try:
            data = json.loads(self.model_path.read_text(encoding="utf-8"))
            self.user_factors = {k: np.asarray(v, dtype=np.float32) for k, v in data.get("user_factors", {}).items()}
            self.item_factors = {k: np.asarray(v, dtype=np.float32) for k, v in data.get("item_factors", {}).items()}
            self.user_index = {k: int(v) for k, v in data.get("user_index", {}).items()}
            self.item_index = {k: int(v) for k, v in data.get("item_index", {}).items()}
            self.user_bias = {k: float(v) for k, v in data.get("user_bias", {}).items()}
            self.item_bias = {k: float(v) for k, v in data.get("item_bias", {}).items()}
            self.job_meta = data.get("job_meta", {})
            self.global_bias = float(data.get("global_bias", 0.0))
            self.feedback_events = int(data.get("feedback_events", 0))
            self.job_upserts = int(data.get("job_upserts", 0))
            self.last_trained_at = data.get("last_trained_at")
        except (OSError, json.JSONDecodeError, ValueError):
            return

    def save(self) -> None:
        if not self.autosave:
            return
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "model_version": MODEL_VERSION,
            "dim": self.dim,
            "user_factors": {k: v.tolist() for k, v in self.user_factors.items()},
            "item_factors": {k: v.tolist() for k, v in self.item_factors.items()},
            "user_index": self.user_index,
            "item_index": self.item_index,
            "user_bias": self.user_bias,
            "item_bias": self.item_bias,
            "job_meta": self.job_meta,
            "global_bias": self.global_bias,
            "feedback_events": self.feedback_events,
            "job_upserts": self.job_upserts,
            "last_trained_at": self.last_trained_at,
            "neumf_checkpoint": str(self.model_path.with_name("online_neumf.pt")),
            "architecture": "NeuMF(GMF+MLP)-online",
        }
        self.model_path.write_text(json.dumps(data), encoding="utf-8")

    def _user_vector(self, user_id: str, profile_text: str | None, user_embedding: list[float] | None) -> np.ndarray:
        if user_id not in self.user_factors:
            seed = f"user:{user_id}:{profile_text or ''}"
            profile_vec = _project_embedding(user_embedding, seed)
            self.user_factors[user_id] = profile_vec.astype(np.float32)
            self.user_bias.setdefault(user_id, 0.0)
        return self.user_factors[user_id]

    def _item_vector(self, job_id: str, embedding: list[float] | None = None, text_seed: str = "") -> np.ndarray:
        if job_id not in self.item_factors:
            self.item_factors[job_id] = _project_embedding(embedding, f"job:{job_id}:{text_seed}").astype(np.float32)
            self.item_bias.setdefault(job_id, 0.0)
        return self.item_factors[job_id]

    def predict_one(
        self,
        user_id: str,
        job_id: str,
        profile_text: str | None = None,
        user_embedding: list[float] | None = None,
        job_embedding: list[float] | None = None,
        text_seed: str = "",
    ) -> float:
        user_vec = self._user_vector(user_id, profile_text, user_embedding)
        item_vec = self._item_vector(job_id, job_embedding, text_seed)
        factor_raw = float(
            np.multiply(user_vec, item_vec).sum()
            + self.user_bias.get(user_id, 0.0)
            + self.item_bias.get(job_id, 0.0)
            + self.global_bias
        )
        return round(_sigmoid(factor_raw), 6)

    def learn_one(
        self,
        user_id: str,
        job_id: str,
        target: float,
        profile_text: str | None = None,
        user_embedding: list[float] | None = None,
        job_embedding: list[float] | None = None,
    ) -> float:
        user_vec = self._user_vector(user_id, profile_text, user_embedding)
        item_vec = self._item_vector(job_id, job_embedding)
        pred = self.predict_one(user_id, job_id, profile_text, user_embedding, job_embedding)
        error = float(target) - pred
        old_user = user_vec.copy()
        self.user_factors[user_id] = user_vec + self.lr * (error * item_vec - self.reg * user_vec)
        self.item_factors[job_id] = item_vec + self.lr * (error * old_user - self.reg * item_vec)
        self.user_bias[user_id] = self.user_bias.get(user_id, 0.0) + self.lr * (error - self.reg * self.user_bias.get(user_id, 0.0))
        self.item_bias[job_id] = self.item_bias.get(job_id, 0.0) + self.lr * (error - self.reg * self.item_bias.get(job_id, 0.0))
        self.global_bias += self.lr * 0.05 * error
        self.feedback_events += 1
        self.last_trained_at = time.time()
        return abs(error)

    def upsert_jobs(self, jobs: list[CandidateJob]) -> int:
        for job in jobs:
            text_seed = f"{job.title} {job.description} {' '.join(job.tags)}"
            current = self.item_factors.get(job.id)
            incoming = _project_embedding(job.embedding, f"job:{job.id}:{text_seed}")
            if current is None:
                self.item_factors[job.id] = incoming.astype(np.float32)
            else:
                blended = (0.97 * current) + (0.03 * incoming)
                self.item_factors[job.id] = (blended / max(float(np.linalg.norm(blended)), 1e-9)).astype(np.float32)
            self.item_bias.setdefault(job.id, 0.0)
            self.job_meta[job.id] = job.model_dump(exclude={"embedding"})
            self.job_upserts += 1
        self.save()
        return len(jobs)

    def register_jobs(self, jobs: list[CandidateJob]) -> int:
        """Update in-memory candidate factors without triggering disk I/O."""
        for job in jobs:
            text_seed = f"{job.title} {job.description} {' '.join(job.tags)}"
            current = self.item_factors.get(job.id)
            incoming = _project_embedding(job.embedding, f"job:{job.id}:{text_seed}")
            if current is None:
                self.item_factors[job.id] = incoming.astype(np.float32)
            else:
                blended = (0.97 * current) + (0.03 * incoming)
                self.item_factors[job.id] = (blended / max(float(np.linalg.norm(blended)), 1e-9)).astype(np.float32)
            self.item_bias.setdefault(job.id, 0.0)
            self.job_meta[job.id] = job.model_dump(exclude={"embedding"})
            self.job_upserts += 1
        return len(jobs)

    def recommend(self, request: NCFRequest) -> list[NCFScore]:
        requested = min(max(int(request.n_items), 0), 1000)
        if requested == 0:
            return []
        candidates = request.candidates or []
        if candidates:
            self.upsert_jobs(candidates)
            ids = [candidate.id for candidate in candidates[:requested]]
            by_id = {candidate.id: candidate for candidate in candidates}
        else:
            ids = (
                (request.candidate_job_ids or list(self.item_factors.keys()))[:requested]
                or [str(i) for i in range(requested)]
            )
            by_id = {}
        scored: list[NCFScore] = []
        for job_id in ids:
            candidate = by_id.get(str(job_id))
            text_seed = ""
            embedding = None
            if candidate is not None:
                text_seed = f"{candidate.title} {candidate.description} {' '.join(candidate.tags)}"
                embedding = candidate.embedding
            score = self.predict_one(
                user_id=str(request.user_id),
                job_id=str(job_id),
                profile_text=request.profile_text,
                user_embedding=request.user_embedding,
                job_embedding=embedding,
                text_seed=text_seed,
            )
            scored.append(NCFScore(job_id=str(job_id), score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:requested]


class OnlineNCF:
    """Online NeuMF model trained with exposure-aware implicit feedback."""

    def __init__(
        self,
        dim: int = FACTOR_DIM,
        lr: float = LEARNING_RATE,
        reg: float = REGULARIZATION,
        *,
        model_path: Path | None = None,
        autosave: bool = True,
        load_existing: bool = True,
    ) -> None:
        self.dim = dim
        self.lr = lr
        self.reg = reg
        self.model_path = model_path or MODEL_PATH
        self.neumf_checkpoint_path = self.model_path.with_name("online_neumf.pt")
        self.autosave = autosave
        self.mf = OnlineMF(dim=dim, lr=lr, reg=reg, model_path=self.model_path, autosave=False, load_existing=load_existing)
        self.user_index: dict[str, int] = {}
        self.item_index: dict[str, int] = {}
        self.user_observed: dict[str, set[str]] = {}
        self.item_interactions: dict[str, int] = {}
        self.job_meta: dict[str, Any] = {}
        self.feedback_events = 0
        self.job_upserts = 0
        self.last_trained_at: float | None = None
        self.neumf_embedding_dim = min(32, max(8, dim))
        self.neumf_hidden_dim = max(32, self.neumf_embedding_dim * 2)
        self.device = torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu") if torch is not None else None
        self.neumf_model = None
        self.neumf_optimizer = None
        self._lock = threading.RLock()
        if load_existing:
            self.user_index = dict(self.mf.user_index)
            self.item_index = dict(self.mf.item_index)
            self.job_meta = dict(self.mf.job_meta)
            self.feedback_events = self.mf.feedback_events
            self.job_upserts = self.mf.job_upserts
            self.last_trained_at = self.mf.last_trained_at
            self._load_neumf_checkpoint()
        self._ensure_neumf_capacity()

    @property
    def user_factors(self) -> dict[str, np.ndarray]:
        return self.mf.user_factors

    @property
    def item_factors(self) -> dict[str, np.ndarray]:
        return self.mf.item_factors

    @property
    def user_bias(self) -> dict[str, float]:
        return self.mf.user_bias

    @property
    def item_bias(self) -> dict[str, float]:
        return self.mf.item_bias

    @property
    def global_bias(self) -> float:
        return self.mf.global_bias

    def _load_neumf_checkpoint(self) -> None:
        if torch is None or not self.neumf_checkpoint_path.exists():
            return
        try:
            checkpoint = torch.load(self.neumf_checkpoint_path, map_location=self.device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                required_users = max(1, len(checkpoint.get("user_index", {})))
                required_items = max(1, len(checkpoint.get("item_index", {})))
                self.neumf_model = NeuralCF(
                    num_users=required_users,
                    num_items=required_items,
                    embedding_dim=self.neumf_embedding_dim,
                    hidden_dim=self.neumf_hidden_dim,
                ).to(self.device)
                self.neumf_model.load_state_dict(checkpoint["model_state_dict"])
                self.neumf_optimizer = torch.optim.AdamW(
                    self.neumf_model.parameters(),
                    lr=max(1e-4, min(0.01, self.lr * 0.2)),
                    weight_decay=self.reg,
                )
                self.neumf_optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                self.user_index = checkpoint.get("user_index", {})
                self.item_index = checkpoint.get("item_index", {})
                self.user_observed = {k: set(v) for k, v in checkpoint.get("user_observed", {}).items()}
                self.item_interactions = checkpoint.get("item_interactions", {})
                self.job_meta = checkpoint.get("job_meta", {})
                self.feedback_events = checkpoint.get("feedback_events", 0)
                self.job_upserts = checkpoint.get("job_upserts", 0)
                self.last_trained_at = checkpoint.get("last_trained_at")
            else:
                required_users = max(1, len(self.user_index))
                required_items = max(1, len(self.item_index))
                self.neumf_model = NeuralCF(
                    num_users=required_users,
                    num_items=required_items,
                    embedding_dim=self.neumf_embedding_dim,
                    hidden_dim=self.neumf_hidden_dim,
                ).to(self.device)
                self.neumf_model.load_state_dict(checkpoint)
                self.neumf_optimizer = torch.optim.AdamW(
                    self.neumf_model.parameters(),
                    lr=max(1e-4, min(0.01, self.lr * 0.2)),
                    weight_decay=self.reg,
                )
        except (OSError, RuntimeError, ValueError):
            self.neumf_model = None
            self.neumf_optimizer = None
            return

    def save(self) -> None:
        with self._lock:
            if not self.autosave:
                return
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "model_version": MODEL_VERSION,
                "dim": self.dim,
                "user_factors": {k: v.tolist() for k, v in self.mf.user_factors.items()},
                "item_factors": {k: v.tolist() for k, v in self.mf.item_factors.items()},
                "user_index": self.user_index,
                "item_index": self.item_index,
                "user_bias": self.mf.user_bias,
                "item_bias": self.mf.item_bias,
                "job_meta": self.job_meta,
                "global_bias": self.mf.global_bias,
                "feedback_events": self.feedback_events,
                "job_upserts": self.job_upserts,
                "last_trained_at": self.last_trained_at,
                "neumf_checkpoint": str(self.neumf_checkpoint_path),
                "architecture": "NeuMF(GMF+MLP)-online",
            }
            self.model_path.write_text(json.dumps(data), encoding="utf-8")
            if torch is not None and self.neumf_model is not None and self.neumf_optimizer is not None:
                checkpoint = {
                    "model_state_dict": self.neumf_model.state_dict(),
                    "optimizer_state_dict": self.neumf_optimizer.state_dict(),
                    "user_index": self.user_index,
                    "item_index": self.item_index,
                    "user_observed": {k: list(v) for k, v in self.user_observed.items()},
                    "item_interactions": self.item_interactions,
                    "job_meta": self.job_meta,
                    "feedback_events": self.feedback_events,
                    "job_upserts": self.job_upserts,
                    "last_trained_at": self.last_trained_at,
                }
                torch.save(checkpoint, self.neumf_checkpoint_path)

    def _ensure_user_index(self, user_id: str) -> int:
        if user_id not in self.user_index:
            self.user_index[user_id] = len(self.user_index)
            self._ensure_neumf_capacity()
        return self.user_index[user_id]

    def _ensure_item_index(self, job_id: str) -> int:
        if job_id not in self.item_index:
            self.item_index[job_id] = len(self.item_index)
            self._ensure_neumf_capacity()
        return self.item_index[job_id]

    def _ensure_neumf_capacity(self) -> None:
        if torch is None or nn is None:
            return
        required_users = max(1, len(self.user_index))
        required_items = max(1, len(self.item_index))
        if (
            self.neumf_model is not None
            and self.neumf_model.user_gmf.num_embeddings >= required_users
            and self.neumf_model.item_gmf.num_embeddings >= required_items
        ):
            return

        old_model = self.neumf_model
        new_model = NeuralCF(
            num_users=required_users,
            num_items=required_items,
            embedding_dim=self.neumf_embedding_dim,
            hidden_dim=self.neumf_hidden_dim,
        ).to(self.device)
        if old_model is not None:
            self._copy_neumf_weights(old_model, new_model)
        self.neumf_model = new_model
        self.neumf_optimizer = torch.optim.AdamW(
            self.neumf_model.parameters(),
            lr=max(1e-4, min(0.01, self.lr * 0.2)),
            weight_decay=self.reg,
        )

    @staticmethod
    def _copy_embedding(old_embedding: nn.Embedding, new_embedding: nn.Embedding) -> None:
        rows = min(old_embedding.weight.shape[0], new_embedding.weight.shape[0])
        cols = min(old_embedding.weight.shape[1], new_embedding.weight.shape[1])
        with torch.no_grad():
            new_embedding.weight[:rows, :cols].copy_(old_embedding.weight[:rows, :cols])

    @staticmethod
    def _copy_linear(old_linear: nn.Linear, new_linear: nn.Linear) -> None:
        rows = min(old_linear.weight.shape[0], new_linear.weight.shape[0])
        cols = min(old_linear.weight.shape[1], new_linear.weight.shape[1])
        with torch.no_grad():
            new_linear.weight[:rows, :cols].copy_(old_linear.weight[:rows, :cols])
            if old_linear.bias is not None and new_linear.bias is not None:
                new_linear.bias[:rows].copy_(old_linear.bias[:rows])

    def _copy_neumf_weights(self, old_model: NeuralCF, new_model: NeuralCF) -> None:
        self._copy_embedding(old_model.user_gmf, new_model.user_gmf)
        self._copy_embedding(old_model.item_gmf, new_model.item_gmf)
        self._copy_embedding(old_model.user_mlp, new_model.user_mlp)
        self._copy_embedding(old_model.item_mlp, new_model.item_mlp)
        old_linears = [module for module in old_model.mlp if isinstance(module, nn.Linear)]
        new_linears = [module for module in new_model.mlp if isinstance(module, nn.Linear)]
        for old_linear, new_linear in zip(old_linears, new_linears):
            self._copy_linear(old_linear, new_linear)
        self._copy_linear(old_model.out, new_model.out)

    def _sample_negatives(self, user_id: str, n: int = 4) -> list[str]:
        observed = self.user_observed.get(user_id, set())
        all_items = list(self.item_index.keys())
        if not all_items:
            return []
        pool = [item for item in all_items if item not in observed]
        if len(pool) <= n:
            return pool
        return random.sample(pool, n)

    def predict_one(
        self,
        user_id: str,
        job_id: str,
        profile_text: str | None = None,
        user_embedding: list[float] | None = None,
        job_embedding: list[float] | None = None,
        text_seed: str = "",
    ) -> float:
        with self._lock:
            if torch is not None and self.neumf_model is not None:
                user_idx = self._ensure_user_index(user_id)
                item_idx = self._ensure_item_index(job_id)
                model = self.neumf_model
                model.eval()
                with torch.inference_mode():
                    logit = model(
                        torch.tensor([user_idx], dtype=torch.long, device=self.device),
                        torch.tensor([item_idx], dtype=torch.long, device=self.device),
                    )
                return round(float(_sigmoid(float(logit.item()))), 6)
            return self.mf.predict_one(user_id, job_id, profile_text, user_embedding, job_embedding, text_seed)

    def learn_one(
        self,
        user_id: str,
        job_id: str,
        target: float,
        profile_text: str | None = None,
        user_embedding: list[float] | None = None,
        job_embedding: list[float] | None = None,
    ) -> float:
        with self._lock:
            self.user_observed.setdefault(user_id, set()).add(job_id)
            if target > 0:
                self.item_interactions[job_id] = self.item_interactions.get(job_id, 0) + 1

            mf_loss = self.mf.learn_one(user_id, job_id, target, profile_text, user_embedding, job_embedding)
            self._learn_neumf(user_id, job_id, target)

            self.feedback_events += 1
            self.last_trained_at = time.time()
            self.mf.feedback_events = self.feedback_events
            self.mf.last_trained_at = self.last_trained_at
            return mf_loss

    def _learn_neumf(self, user_id: str, job_id: str, target: float, num_negatives: int = 4) -> None:
        if torch is None or nn is None or self.neumf_model is None or self.neumf_optimizer is None:
            return
        user_idx = self._ensure_user_index(user_id)
        item_idx = self._ensure_item_index(job_id)

        users = [user_idx]
        items = [item_idx]
        labels = [float(target)]

        if target > 0:
            negatives = self._sample_negatives(user_id, n=num_negatives)
            for neg_job_id in negatives:
                neg_item_idx = self._ensure_item_index(neg_job_id)
                users.append(user_idx)
                items.append(neg_item_idx)
                labels.append(0.0)

        self.neumf_model.train()
        users_t = torch.tensor(users, dtype=torch.long, device=self.device)
        items_t = torch.tensor(items, dtype=torch.long, device=self.device)
        labels_t = torch.tensor(labels, dtype=torch.float32, device=self.device)
        logits = self.neumf_model(users_t, items_t)
        loss = nn.BCEWithLogitsLoss()(logits, labels_t)
        self.neumf_optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.neumf_model.parameters(), max_norm=1.0)
        self.neumf_optimizer.step()

    def upsert_jobs(self, jobs: list[CandidateJob]) -> int:
        with self._lock:
            count = self.register_jobs(jobs)
            self.save()
            return count

    def register_jobs(self, jobs: list[CandidateJob]) -> int:
        """Register candidates for scoring without checkpointing every request."""
        count = self.mf.register_jobs(jobs)
        for job in jobs:
            self._ensure_item_index(job.id)
            self.job_meta[job.id] = self.mf.job_meta.get(job.id, {})
        self.job_upserts = self.mf.job_upserts
        return count

    def recommend(self, request: NCFRequest) -> list[NCFScore]:
        requested = min(max(int(request.n_items), 0), 1000)
        if requested == 0:
            return []
        with self._lock:
            candidates = request.candidates or []
            if candidates:
                self.register_jobs(candidates)
                ids = [candidate.id for candidate in candidates[:requested]]
                by_id = {candidate.id: candidate for candidate in candidates}
            else:
                ids = (
                    (request.candidate_job_ids or list(self.item_index.keys()))[:requested]
                    or [str(i) for i in range(requested)]
                )
                by_id = {}

            user_id = str(request.user_id)
            user_idx = self._ensure_user_index(user_id)

            item_indices = []
            valid_ids = []
            for job_id in ids:
                item_indices.append(self._ensure_item_index(job_id))
                valid_ids.append(job_id)

            neumf_scores: dict[str, float] = {}
            if torch is not None and self.neumf_model is not None and valid_ids:
                model = self.neumf_model
                model.eval()
                with torch.inference_mode():
                    user_tensor = torch.tensor([user_idx] * len(item_indices), dtype=torch.long, device=self.device)
                    item_tensor = torch.tensor(item_indices, dtype=torch.long, device=self.device)
                    logits = model(user_tensor, item_tensor)
                    probs = torch.sigmoid(logits).cpu().numpy()
                for job_id, prob in zip(valid_ids, probs):
                    neumf_scores[job_id] = round(float(prob), 6)

            scored: list[NCFScore] = []
            for job_id in valid_ids:
                candidate = by_id.get(str(job_id))
                text_seed = ""
                embedding = None
                if candidate is not None:
                    text_seed = f"{candidate.title} {candidate.description} {' '.join(candidate.tags)}"
                    embedding = candidate.embedding
                neumf_score = neumf_scores.get(job_id, 0.0)
                mf_score = self.mf.predict_one(user_id, job_id, request.profile_text, request.user_embedding, embedding, text_seed)
                pop_score = self.item_interactions.get(job_id, 0)
                scored.append(NCFScore(
                    job_id=str(job_id),
                    score=neumf_score,
                    mf_score=mf_score,
                    pop_score=pop_score,
                ))
            scored.sort(key=lambda item: item.score, reverse=True)
            return scored[:requested]


model = OnlineNCF()
app = FastAPI(title="SCPA Online NCF Service", version="2.0.0")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "ncf",
        "model_version": MODEL_VERSION,
        "model_type": "NeuMF" if (torch is not None and model.neumf_model is not None) else "OnlineMF",
        "users": len(model.user_factors),
        "items": len(model.item_factors),
        "feedback_events": model.feedback_events,
    }


@app.post("/jobs/upsert")
async def upsert_jobs(request: JobUpsertRequest) -> dict[str, Any]:
    count = model.upsert_jobs(request.jobs)
    return {"status": "ok", "upserted": count, "items": len(model.item_factors)}


@app.post("/feedback")
async def feedback(event: FeedbackEvent) -> dict[str, Any]:
    target = float(event.value) if event.value is not None else EVENT_TARGETS.get(event.event, 0.2)
    loss = model.learn_one(
        user_id=str(event.user_id),
        job_id=event.job_id,
        target=target,
        profile_text=event.profile_text,
        user_embedding=event.user_embedding,
        job_embedding=event.job_embedding,
    )
    model.save()
    return {"status": "trained", "target": target, "absolute_error": round(loss, 6), "feedback_events": model.feedback_events}


@app.post("/train")
async def train(events: list[FeedbackEvent] | None = None) -> dict[str, Any]:
    events = events or [
        FeedbackEvent(user_id="bootstrap", job_id="job-mc", event="click", profile_text="Sastra Inggris Public Speaking"),
        FeedbackEvent(user_id="bootstrap", job_id="job-backend", event="skip", profile_text="Sastra Inggris Public Speaking"),
    ]
    losses = []
    for event in events:
        target = float(event.value) if event.value is not None else EVENT_TARGETS.get(event.event, 0.2)
        losses.append(model.learn_one(str(event.user_id), event.job_id, target, event.profile_text, event.user_embedding, event.job_embedding))
    model.save()
    return {"status": "trained", "events": len(events), "mean_absolute_error": round(float(np.mean(losses)), 6)}


@app.post("/predict", response_model=NCFResponse)
async def predict(request: NCFRequest) -> NCFResponse:
    return await recommend_ncf(request)


@app.post("/recommend/ncf", response_model=NCFResponse)
async def recommend_ncf(request: NCFRequest) -> NCFResponse:
    return NCFResponse(user_id=str(request.user_id), recommendations=model.recommend(request))


@app.post("/users/{user_id}/invalidate")
async def invalidate_user(user_id: str) -> dict[str, Any]:
    """Drop the cached embedding/bias for ``user_id``.

    Called by the pipeline whenever a user's profile (skills, major, etc.) is
    updated so the next recommendation request rebuilds the user vector from
    the fresh ``profile_text`` instead of reusing the stale cached one.
    """
    uid = str(user_id)
    factor_existed = model.user_factors.pop(uid, None) is not None
    bias_existed = model.user_bias.pop(uid, None) is not None
    model.save()
    return {
        "status": "ok",
        "user_id": uid,
        "factor_invalidated": factor_existed,
        "bias_invalidated": bias_existed,
    }


@app.get("/model/status")
@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "service": "ncf",
        "model_version": MODEL_VERSION,
        "metrics": {
            "users": len(model.user_factors),
            "items": len(model.item_factors),
            "feedback_events": model.feedback_events,
            "job_upserts": model.job_upserts,
            "factor_dim": model.dim,
            "learning_rate": model.lr,
            "regularization": model.reg,
            "last_trained_at": model.last_trained_at,
        },
    }
