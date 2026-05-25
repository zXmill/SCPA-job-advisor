"""Online DQN reranker for real-time job recommendation.

The service uses a PyTorch QNetwork, replay buffer, epsilon-greedy action
selection, and a soft-updated target network. It consumes scrape features plus
SBERT/NCF scores, stores transition provenance, and updates the policy from
reward feedback.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
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

logger = logging.getLogger("scpa.dqn")

# Optional PostgreSQL replay archive. Import fails gracefully when db module
# is unavailable (e.g. isolated test environments without the full repo).
_DBNC = None
try:
    import sys

    _project_root = Path(__file__).resolve().parent.parent.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    _DBNC = True
except Exception:  # pragma: no cover
    _DBNC = False


MODEL_VERSION = "online-dqn-v2"
EMBED_DIM = int(os.getenv("DQN_EMBED_DIM", "64"))
FEATURE_DIM = EMBED_DIM + 6
LEARNING_RATE = float(os.getenv("DQN_LEARNING_RATE", "0.03"))
GAMMA = float(os.getenv("DQN_GAMMA", "0.92"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(Path(__file__).resolve().parent / "weights")))
MODEL_PATH = MODEL_DIR / "online_dqn.json"

# -- Optional PostgreSQL replay archive --
_DQNEngine = None
_DQNSession: async_sessionmaker | None = None


def _dqn_db_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _ensure_dqn_db() -> None:
    global _DQNEngine, _DQNSession
    if _DQNSession is not None or not _DBNC:
        return
    url = _dqn_db_url()
    if not url:
        return
    try:
        _DQNEngine = create_async_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=5)
        _DQNSession = async_sessionmaker(_DQNEngine, class_=AsyncSession, expire_on_commit=False)
    except Exception as exc:
        logger.warning("DQN DB init skipped: %s", exc)


async def _persist_replay(
    user_id: str,
    state: list[float],
    action: int,
    reward: float,
    next_state: list[float],
    done: bool,
) -> None:
    if not _DBNC or _DQNSession is None:
        return
    try:
        async with _DQNSession() as session:
            await session.execute(
                text(
                    "INSERT INTO dqn_replay_archive ("
                    "user_id, state, action, reward, next_state, done, created_at"
                    ") VALUES ("
                    ":uid, :state, :action, :reward, :next_state, :done, NOW()"
                    ")"
                ),
                {
                    "uid": user_id if _is_uuid(user_id) else None,
                    "state": state,
                    "action": action,
                    "reward": reward,
                    "next_state": next_state,
                    "done": done,
                },
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Replay archive write failed: %s", exc)


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (TypeError, ValueError):
        return False


SKILL_VOCAB = [
    "python",
    "sql",
    "postgresql",
    "redis",
    "pandas",
    "numpy",
    "statistics",
    "pytorch",
    "tensorflow",
    "react",
    "next.js",
    "node.js",
    "docker",
    "kubernetes",
    "aws",
    "public speaking",
    "english",
    "event",
    "communication",
    "content writing",
    "translation",
    "business analysis",
    "dashboard",
    "machine learning",
    "fastapi",
    "figma",
    "ux research",
    "prototyping",
    "ui design",
]
ROLE_VOCAB = [
    "Data Scientist",
    "Backend Developer",
    "Fullstack Developer",
    "Business Analyst",
    "Master of Ceremony",
]
ROLE_SKILL_REQUIREMENTS: dict[str, list[str]] = {
    "data scientist": ["Python", "Pandas", "Machine Learning", "Statistics", "SQL", "Dashboard"],
    "backend developer": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
    "fullstack developer": ["React", "Next.js", "Node.js", "SQL", "Docker"],
    "business analyst": ["SQL", "Business Analysis", "Dashboard", "Communication"],
    "master of ceremony": ["Public Speaking", "English", "Event", "Communication"],
    "ui/ux designer": ["Figma", "UI Design", "Prototyping", "UX Research"],
}
ROLE_MILESTONES: dict[str, list[dict[str, Any]]] = {
    "data scientist": [
        {
            "milestone_id": "ml-modeling",
            "title": "Train supervised machine learning models",
            "required_skills": ["Python", "Pandas", "Machine Learning", "Statistics"],
            "reward": 1.0,
        },
        {
            "milestone_id": "sql-analytics",
            "title": "Build SQL analytics workflows",
            "required_skills": ["SQL", "Dashboard"],
            "reward": 0.8,
        },
    ],
    "backend developer": [
        {
            "milestone_id": "fastapi-service",
            "title": "Build production FastAPI services",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "reward": 1.0,
        },
        {
            "milestone_id": "cache-deploy",
            "title": "Add Redis caching and Docker deployment",
            "required_skills": ["Redis", "Docker"],
            "reward": 0.8,
        },
    ],
    "business analyst": [
        {
            "milestone_id": "dashboard-storytelling",
            "title": "Create dashboard-based business recommendations",
            "required_skills": ["SQL", "Business Analysis", "Dashboard"],
            "reward": 1.0,
        },
    ],
    "master of ceremony": [
        {
            "milestone_id": "public-speaking-advanced",
            "title": "Practice advanced public speaking",
            "required_skills": ["Public Speaking", "English"],
            "reward": 1.0,
        },
        {
            "milestone_id": "event-protocol",
            "title": "Learn event protocol and audience management",
            "required_skills": ["Event", "Communication"],
            "reward": 0.8,
        },
    ],
    "ui/ux designer": [
        {
            "milestone_id": "figma-research",
            "title": "Run user research and prototype in Figma",
            "required_skills": ["Figma", "UX Research", "Prototyping"],
            "reward": 1.0,
        },
    ],
}
N_ACTIONS = len(SKILL_VOCAB)


if nn is not None:
    class QNetwork(nn.Module):
        """Feed-forward Q-network used for DQN checkpoints."""

        def __init__(self, state_dim: int, n_actions: int, hidden_dim: int = 128) -> None:
            super().__init__()
            self.layers = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, n_actions),
            )

        def forward(self, states):
            return self.layers(states)
else:
    class QNetwork:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyTorch is required for QNetwork")


EVENT_REWARDS = {
    "click": 1.0,
    "apply": 1.0,
    "view_10s": 0.5,
    "long_view": 0.5,
    "view": 0.5,
    "skip": -0.5,
    "immediate_skip": -0.5,
    "skip_immediately": -0.5,
    "domain_mismatch": -1.0,
}


@dataclass(frozen=True)
class Transition:
    """Immutable DQN replay entry."""

    user_id: str
    job_id: str | None
    state: list[float]
    action: int
    action_label: str
    reward: float
    next_state: list[float]
    done: bool
    policy_source: str = "qnetwork_policy"
    model_version: str = MODEL_VERSION


class RankRequest(BaseModel):
    user_id: int | str
    job_candidates: list[dict[str, Any]]
    session_ctx: dict[str, Any] = Field(default_factory=dict)


class RerankRequest(BaseModel):
    user_id: int | str
    session_history: list[dict[str, Any]] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class RewardUpdateRequest(BaseModel):
    user_id: int | str
    job_id: str | None = None
    action: int | str | None = None
    event: str = "view"
    reward: float | None = None
    same_domain: bool = True
    state: dict[str, Any] | None = None
    next_state: dict[str, Any] | None = None
    job: dict[str, Any] | None = None
    done: bool = False


class JobUpsertRequest(BaseModel):
    jobs: list[dict[str, Any]]


class LearningPathRequest(BaseModel):
    user_id: int | str
    current_skills: list[str] = Field(default_factory=list)
    target_role: str = "Data Scientist"
    profile_text: str | None = None
    market_demand: dict[str, float] = Field(default_factory=dict)
    max_steps: int = Field(default=8, ge=1, le=12)


class RecommendDQNRequest(BaseModel):
    user_id: int | str
    state: list[float] | None = None
    job: dict[str, Any] = Field(default_factory=dict)
    session_ctx: dict[str, Any] = Field(default_factory=dict)


class FeedbackDQNRequest(BaseModel):
    user_id: int | str
    state: list[float]
    action: int | str | None = None
    reward: float = 0.0
    next_state: list[float]
    done: bool = False
    event: str = "feedback"


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


def _project_embedding(values: list[float] | None, seed: str, dim: int = EMBED_DIM) -> np.ndarray:
    if values:
        arr = np.asarray(values, dtype=np.float32)
        if arr.size >= dim:
            chunks = np.array_split(arr, dim)
            vec = np.asarray([float(chunk.mean()) for chunk in chunks], dtype=np.float32)
        else:
            vec = np.tile(arr, math.ceil(dim / arr.size))[:dim]
    else:
        import hashlib

        digest = hashlib.blake2b(seed.encode("utf-8", "ignore"), digest_size=64).digest()
        raw = np.frombuffer(digest, dtype=np.uint8).astype(np.float32)
        vec = np.tile(raw, math.ceil(dim / raw.size))[:dim]
        vec = (vec / 127.5) - 1.0
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def reward_value(event: str, same_domain: bool = True, explicit_reward: float | None = None) -> float:
    base = float(explicit_reward) if explicit_reward is not None else EVENT_REWARDS.get(event, 0.0)
    if not same_domain:
        base *= 0.2
    return float(max(-1.0, min(1.0, base)))


class ReplayBuffer:
    """Bounded replay store for DQN transition entries."""

    def __init__(self, capacity: int = 10_000, min_size: int = 32) -> None:
        self.buffer: deque[Transition] = deque(maxlen=capacity)
        self.min_size = min_size

    def push(self, transition: Transition) -> None:
        self.buffer.append(transition)

    def sample(self, batch_size: int) -> list[Transition]:
        size = min(max(batch_size, 0), len(self.buffer))
        if size == 0:
            return []
        return random.sample(list(self.buffer), size)

    def to_list(self) -> list[dict[str, Any]]:
        return [
            {
                "user_id": t.user_id,
                "job_id": t.job_id,
                "state": t.state,
                "action": t.action,
                "action_label": t.action_label,
                "reward": t.reward,
                "next_state": t.next_state,
                "done": t.done,
                "policy_source": t.policy_source,
                "model_version": t.model_version,
            }
            for t in self.buffer
        ]

    def load(self, rows: list[dict[str, Any]]) -> None:
        self.buffer.clear()
        fields = {f for f in Transition.__dataclass_fields__}
        for row in rows[-self.buffer.maxlen :]:
            kwargs = {k: v for k, v in row.items() if k in fields}
            self.buffer.append(Transition(**kwargs))

    def __len__(self) -> int:
        return len(self.buffer)


class OnlineDQN:
    def __init__(
        self,
        model_path: Path | None = None,
        *,
        autosave: bool = True,
        load_existing: bool = True,
    ) -> None:
        self.model_path = Path(model_path) if model_path is not None else MODEL_PATH
        self.checkpoint_path = self.model_path.with_name("online_dqn.pt")
        self.autosave = autosave
        self.replay = ReplayBuffer(capacity=10_000, min_size=32)
        self.jobs: dict[str, dict[str, Any]] = {}
        self.training_steps = 0
        self.job_upserts = 0
        self.last_trained_at: float | None = None
        self.epsilon = float(os.getenv("DQN_EPSILON", "0.12"))
        self.epsilon_min = float(os.getenv("DQN_EPSILON_MIN", "0.02"))
        self.epsilon_decay = float(os.getenv("DQN_EPSILON_DECAY", "0.995"))
        self.target_sync_interval = int(os.getenv("DQN_TARGET_SYNC_INTERVAL", "10"))
        self.min_replay_size = int(os.getenv("DQN_MIN_REPLAY_SIZE", "32"))
        self.device = torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu") if torch is not None else None
        self.policy_net = None
        self.target_net = None
        self.optimizer = None
        self._init_networks()
        if load_existing:
            self._load()
            self._load_checkpoint()

    def _init_networks(self) -> None:
        if torch is None or nn is None:
            return
        torch.manual_seed(17)
        self.policy_net = QNetwork(FEATURE_DIM, N_ACTIONS).to(self.device)
        self.target_net = QNetwork(FEATURE_DIM, N_ACTIONS).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.optimizer = torch.optim.AdamW(
            self.policy_net.parameters(),
            lr=min(0.01, max(1e-4, LEARNING_RATE * 0.2)),
            weight_decay=1e-4,
        )

    def _load(self) -> None:
        if not self.model_path.exists():
            return
        try:
            data = json.loads(self.model_path.read_text(encoding="utf-8"))
            self.jobs = data.get("jobs", {})
            self.training_steps = int(data.get("training_steps", 0))
            self.job_upserts = int(data.get("job_upserts", 0))
            self.last_trained_at = data.get("last_trained_at")
            self.epsilon = float(data.get("epsilon", self.epsilon))
            self.replay.load(data.get("replay", []))
        except (OSError, json.JSONDecodeError, ValueError):
            return

    def _load_checkpoint(self) -> None:
        if torch is None or self.policy_net is None or self.target_net is None:
            return
        if not self.checkpoint_path.exists():
            return
        try:
            checkpoint = torch.load(
                self.checkpoint_path,
                map_location=self.device,
                weights_only=True,
            )
            self.policy_net.load_state_dict(checkpoint["policy_net"])
            self.target_net.load_state_dict(checkpoint["target_net"])
        except (OSError, RuntimeError, KeyError, ValueError):
            return

    def save(self) -> None:
        if not self.autosave:
            return
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "model_version": MODEL_VERSION,
            "jobs": self.jobs,
            "training_steps": self.training_steps,
            "job_upserts": self.job_upserts,
            "last_trained_at": self.last_trained_at,
            "epsilon": self.epsilon,
            "replay": self.replay.to_list()[-500:],
            "checkpoint": str(self.checkpoint_path),
            "architecture": "DQN(QNetwork+ReplayBuffer+target_net)",
        }
        self.model_path.write_text(json.dumps(data), encoding="utf-8")
        if torch is not None and self.policy_net is not None and self.target_net is not None:
            torch.save(
                {
                    "policy_net": self.policy_net.state_dict(),
                    "target_net": self.target_net.state_dict(),
                },
                self.checkpoint_path,
            )

    def upsert_jobs(self, jobs: list[dict[str, Any]]) -> int:
        for job in jobs:
            job_id = str(job.get("id") or job.get("job_id") or len(self.jobs))
            payload = dict(job)
            payload["id"] = job_id
            self.jobs[job_id] = payload
            self.job_upserts += 1
        self.save()
        return len(jobs)

    def featurize(self, user_id: str, job: dict[str, Any], session_ctx: dict[str, Any] | None = None) -> np.ndarray:
        session_ctx = session_ctx or {}
        job_id = str(job.get("id") or job.get("job_id") or job.get("title") or "unknown")
        embedding = _project_embedding(job.get("embedding"), f"job:{job_id}:{job.get('title', '')}")
        sbert = float(job.get("sbert_score") or 0.0)
        ncf = float(job.get("ncf_score") or 0.0)
        history_count = float(len(session_ctx.get("interaction_history", [])))
        interaction_count = float(session_ctx.get("interaction_count", 0))
        text_len = min(1.0, len(str(job.get("description") or "")) / 1500.0)
        bias = 1.0
        dense = np.asarray([sbert, ncf, math.log1p(history_count) / 5.0, math.log1p(interaction_count) / 5.0, text_len, bias], dtype=np.float32)
        return np.concatenate([embedding, dense]).astype(np.float32)

    def q_values(self, features: np.ndarray, *, target: bool = False) -> np.ndarray:
        values = self.q_values_batch(np.asarray([features]), target=target)
        return values[0] if len(values) else np.zeros(N_ACTIONS, dtype=np.float32)

    def q_values_batch(self, features_batch: np.ndarray, *, target: bool = False) -> np.ndarray:
        batch = np.asarray(features_batch, dtype=np.float32)
        if batch.size == 0:
            return np.zeros((0, N_ACTIONS), dtype=np.float32)
        if batch.ndim == 1:
            batch = batch.reshape(1, -1)
        if torch is None or self.policy_net is None or self.target_net is None:
            return np.zeros((batch.shape[0], N_ACTIONS), dtype=np.float32)
        network = self.target_net if target else self.policy_net
        network.eval()
        with torch.inference_mode():
            values = network(torch.tensor(batch, dtype=torch.float32, device=self.device))
        return values.detach().cpu().numpy().astype(np.float32)

    def q_value(self, features: np.ndarray) -> float:
        return float(np.max(self.q_values(features)))

    def _resolve_action(self, action: int | str | None, features: np.ndarray) -> tuple[int, str, str]:
        if isinstance(action, int):
            index = max(0, min(N_ACTIONS - 1, action))
            return index, SKILL_VOCAB[index], "request_action"
        if isinstance(action, str) and action.strip():
            normalized = action.strip().lower()
            for index, label in enumerate(SKILL_VOCAB):
                if normalized == label.lower():
                    return index, label, "request_action"
        if random.random() < self.epsilon:
            index = random.randrange(N_ACTIONS)
            return index, SKILL_VOCAB[index], "epsilon_explore"
        values = self.q_values(features)
        index = int(np.argmax(values))
        return index, SKILL_VOCAB[index], "qnetwork_policy"

    def _resolve_action_masked(
        self, features: np.ndarray, mastered: set[str]
    ) -> tuple[int, str, str]:
        if random.random() < self.epsilon:
            available = [(i, s) for i, s in enumerate(SKILL_VOCAB) if _skill_key(s) not in mastered]
            if available:
                index, label = random.choice(available)
                return index, label, "epsilon_explore"
        values = self.q_values(features)
        best_index = -1
        best_q = -float("inf")
        best_skill = ""
        for index, skill in enumerate(SKILL_VOCAB):
            if _skill_key(skill) in mastered:
                continue
            if values[index] > best_q:
                best_q = values[index]
                best_index = index
                best_skill = skill
        if best_index == -1:
            return 0, SKILL_VOCAB[0], "fallback"
        return best_index, best_skill, "qnetwork_policy"

    def _train_from_replay(self, batch_size: int = 16) -> float:
        if torch is None or nn is None or self.policy_net is None or self.target_net is None or self.optimizer is None:
            return 0.0
        if len(self.replay) < self.replay.min_size:
            return 0.0
        batch = self.replay.sample(batch_size)
        if not batch:
            return 0.0

        states = torch.tensor(np.asarray([t.state for t in batch]), dtype=torch.float32, device=self.device)
        actions = torch.tensor([t.action for t in batch], dtype=torch.long, device=self.device)
        rewards = torch.tensor([t.reward for t in batch], dtype=torch.float32, device=self.device)
        next_states = torch.tensor(np.asarray([t.next_state for t in batch]), dtype=torch.float32, device=self.device)
        dones = torch.tensor([t.done for t in batch], dtype=torch.bool, device=self.device)

        self.policy_net.train()
        q_pred = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            next_q = self.target_net(next_states).max(dim=1).values
            q_target = rewards + GAMMA * next_q * (~dones).float()
        loss = nn.MSELoss()(q_pred, q_target)
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        self.optimizer.step()
        return float(loss.item())

    def rank(self, user_id: str, jobs: list[dict[str, Any]], session_ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        session_ctx = session_ctx or {}
        current_skills = _as_skill_list(session_ctx.get("skills"))
        target_role = str(session_ctx.get("target_role") or session_ctx.get("program_studi") or "Data Scientist")
        session_market_demand = (
            session_ctx.get("market_demand")
            if isinstance(session_ctx.get("market_demand"), dict)
            else {}
        )
        features_batch = [self.featurize(user_id, job, session_ctx) for job in jobs]
        q_matrix = self.q_values_batch(np.asarray(features_batch, dtype=np.float32))
        for job, q_values in zip(jobs, q_matrix):
            q_raw = float(np.max(q_values)) if len(q_values) else 0.0
            job_skills = _as_skill_list(job.get("skills") or job.get("tags"))
            job_market_demand = dict(session_market_demand)
            for skill in job_skills:
                job_market_demand.setdefault(skill, 0.7)
            skill_state = build_skill_path_state(
                user_id=user_id,
                current_skills=current_skills,
                target_role=target_role,
                market_demand=job_market_demand,
                profile_text=str(session_ctx.get("profile_text") or ""),
            )
            candidate_skills = job_skills or list(skill_state.get("missing_skills") or [])
            candidate_keys = {_skill_key(skill) for skill in candidate_skills}
            missing_candidates = [
                skill
                for skill in skill_state.get("missing_skills", [])
                if _skill_key(skill) in candidate_keys
            ] or list(skill_state.get("missing_skills") or [])
            skill_steps = [
                _build_skill_path_step(
                    index=0,
                    skill=skill,
                    state=skill_state,
                    q_value=float(q_values[_skill_index(skill)]) if len(q_values) > _skill_index(skill) else 0.0,
                    policy_source="skill_path_policy",
                )
                for skill in missing_candidates
            ]
            skill_steps.sort(
                key=lambda step: (
                    float(step["reward_components"]["total_reward"]),
                    float(step["market_demand"]),
                    float(step["priority"]),
                ),
                reverse=True,
            )
            action_step = skill_steps[0] if skill_steps else _fallback_skill_path_step(skill_state)
            action_index = action_step["action"] if isinstance(action_step.get("action"), int) else 0
            action_label = str(action_step.get("action_label") or action_step.get("skill") or SKILL_VOCAB[action_index])
            policy_source = str(action_step.get("policy_source") or "skill_path_policy")
            prior = 0.55 * float(job.get("sbert_score") or 0.0) + 0.35 * float(job.get("ncf_score") or 0.0)
            path_reward = float(action_step["reward_components"]["total_reward"]) / 2.0
            q_value = (0.45 * _sigmoid(q_raw)) + (0.25 * prior) + (0.3 * _clamp01(path_reward))
            ranked.append(
                {
                    "job": job,
                    "q_value": round(float(q_value), 6),
                    "action": action_index,
                    "action_label": action_label,
                    "action_type": action_step.get("action_type"),
                    "policy_source": policy_source,
                    "policy_objective": "skill_path",
                    "reward_components": action_step["reward_components"],
                    "skill_gap": action_step["skill_gap"],
                    "estimated_skill_gap_after": action_step["estimated_skill_gap_after"],
                    "market_demand": action_step["market_demand"],
                }
            )
        ranked.sort(key=lambda item: item["q_value"], reverse=True)
        return ranked

    def learn(self, request: RewardUpdateRequest) -> dict[str, Any]:
        job = request.job or {}
        if request.job_id and not job:
            job = self.jobs.get(request.job_id, {"id": request.job_id})
        if request.job_id and "id" not in job:
            job["id"] = request.job_id
        state_ctx = request.state or {}
        next_ctx = request.next_state or state_ctx
        features = self.featurize(str(request.user_id), job, state_ctx)
        next_features = self.featurize(str(request.user_id), job, next_ctx)
        action_index, action_label, policy_source = self._resolve_action(request.action, features)

        immediate_reward = reward_value(request.event, request.same_domain, request.reward)
        next_values = self.q_values(next_features, target=True)
        target = immediate_reward
        if not request.done and next_values.size > 0:
            target += GAMMA * float(np.max(next_values))
        pred = self.q_value(features)
        td_error = target - pred

        self.replay.push(
            Transition(
                user_id=str(request.user_id),
                job_id=job.get("id"),
                state=features.tolist(),
                action=action_index,
                action_label=action_label,
                reward=immediate_reward,
                next_state=next_features.tolist(),
                done=bool(request.done),
                policy_source=policy_source,
                model_version=MODEL_VERSION,
            )
        )

        loss = 0.0
        if len(self.replay) >= self.min_replay_size:
            loss = self._train_from_replay()
            self.training_steps += 1
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            if self.training_steps % self.target_sync_interval == 0:
                self.soft_update()
            self.last_trained_at = time.time()

        self.save()
        return {
            "target": float(target),
            "prediction": float(pred),
            "td_error": float(td_error),
            "loss": float(loss),
            "action": action_index,
            "action_label": action_label,
            "policy_source": policy_source,
            "replay_size": len(self.replay),
            "wait_for_replay": len(self.replay) < self.min_replay_size,
        }

    def feedback(
        self,
        user_id: int | str,
        state: list[float],
        action: int | str | None,
        reward: float,
        next_state: list[float],
        done: bool = False,
        event: str = "feedback",
    ) -> dict[str, Any]:
        features = np.asarray(state, dtype=np.float32)
        next_features = np.asarray(next_state, dtype=np.float32)
        action_index, action_label, policy_source = self._resolve_action(action, features)

        immediate_reward = reward_value(event, True, reward)
        next_values = self.q_values(next_features, target=True)
        target = immediate_reward
        if not done and next_values.size > 0:
            target += GAMMA * float(np.max(next_values))
        pred = self.q_value(features)
        td_error = target - pred

        self.replay.push(
            Transition(
                user_id=str(user_id),
                job_id=None,
                state=features.tolist(),
                action=action_index,
                action_label=action_label,
                reward=immediate_reward,
                next_state=next_features.tolist(),
                done=done,
                policy_source=policy_source,
                model_version=MODEL_VERSION,
            )
        )

        loss = 0.0
        if len(self.replay) >= self.min_replay_size:
            loss = self._train_from_replay()
            self.training_steps += 1
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
            if self.training_steps % self.target_sync_interval == 0:
                self.soft_update()
            self.last_trained_at = time.time()

        self.save()
        return {
            "target": float(target),
            "prediction": float(pred),
            "td_error": float(td_error),
            "loss": float(loss),
            "action": action_index,
            "action_label": action_label,
            "policy_source": policy_source,
            "replay_size": len(self.replay),
            "wait_for_replay": len(self.replay) < self.min_replay_size,
        }

    def soft_update(self, tau: float = 0.05) -> None:
        if torch is None or self.policy_net is None or self.target_net is None:
            return
        with torch.no_grad():
            for target_param, policy_param in zip(
                self.target_net.parameters(),
                self.policy_net.parameters(),
            ):
                target_param.data.mul_(1.0 - tau).add_(policy_param.data, alpha=tau)


agent = OnlineDQN()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_dqn_db()
    yield


app = FastAPI(title="SCPA Online DQN Service", version="2.0.0", lifespan=lifespan)


def _skill_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("-", " ").split())


def _clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _normalised_demand_map(market_demand: dict[str, float] | None) -> dict[str, float]:
    return {
        _skill_key(skill): _clamp01(float(value))
        for skill, value in (market_demand or {}).items()
        if str(skill).strip()
    }


def _skill_index(skill: str) -> int:
    key = _skill_key(skill)
    for index, label in enumerate(SKILL_VOCAB):
        if _skill_key(label) == key:
            return index
    return 0


def _role_key(target_role: str) -> str:
    key = _skill_key(target_role)
    if key in ROLE_SKILL_REQUIREMENTS:
        return key
    for known in ROLE_SKILL_REQUIREMENTS:
        if key in known or known in key:
            return known
    return "data scientist"


def _role_required_skills(target_role: str) -> list[str]:
    return list(ROLE_SKILL_REQUIREMENTS.get(_role_key(target_role), ROLE_SKILL_REQUIREMENTS["data scientist"]))


def _milestone_for_skill(target_role: str, skill: str) -> dict[str, Any] | None:
    skill_key = _skill_key(skill)
    for milestone in ROLE_MILESTONES.get(_role_key(target_role), []):
        required = {_skill_key(item) for item in milestone.get("required_skills", [])}
        if skill_key in required:
            return milestone
    return None


def _market_demand_for_skill(
    skill: str,
    target_role: str,
    market_demand: dict[str, float] | None,
) -> float:
    demand = _normalised_demand_map(market_demand)
    skill_key = _skill_key(skill)
    if skill_key in demand:
        return demand[skill_key]
    milestone = _milestone_for_skill(target_role, skill)
    if milestone:
        return _clamp01(0.45 + (0.35 * float(milestone.get("reward", 0.0))))
    return 0.5


def _as_skill_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def build_skill_path_state(
    *,
    user_id: int | str,
    current_skills: list[str],
    target_role: str,
    market_demand: dict[str, float] | None = None,
    profile_text: str | None = None,
) -> dict[str, Any]:
    mastered = {_skill_key(skill) for skill in current_skills}
    required_skills = _role_required_skills(target_role)
    missing_skills = [skill for skill in required_skills if _skill_key(skill) not in mastered]
    demand_by_skill = {
        skill: _market_demand_for_skill(skill, target_role, market_demand)
        for skill in required_skills
    }
    return {
        "user_profile": {
            "user_id": str(user_id),
            "target_role": target_role,
            "current_skills": list(current_skills),
            "profile_text": profile_text,
        },
        "required_skills": required_skills,
        "missing_skills": missing_skills,
        "market_demand": demand_by_skill,
        "skill_gap": round(len(missing_skills) / max(1, len(required_skills)), 6),
    }


def _skill_path_reward_components(skill: str, state: dict[str, Any]) -> dict[str, float]:
    missing_skills = list(state.get("missing_skills") or [])
    required_skills = list(state.get("required_skills") or [])
    is_missing = _skill_key(skill) in {_skill_key(item) for item in missing_skills}
    skill_gap_reduction = (1.0 / max(1, len(missing_skills))) if is_missing else 0.0
    job_match_lift = _clamp01(float((state.get("market_demand") or {}).get(skill, 0.0)))
    total_reward = skill_gap_reduction + job_match_lift
    estimated_gap_after = (
        max(0.0, (len(missing_skills) - (1 if is_missing else 0)) / max(1, len(required_skills)))
    )
    return {
        "skill_gap_reduction": round(skill_gap_reduction, 6),
        "job_match_lift": round(job_match_lift, 6),
        "total_reward": round(total_reward, 6),
        "estimated_skill_gap_after": round(estimated_gap_after, 6),
    }


def _action_type_for_skill(target_role: str, skill: str) -> str:
    milestone = _milestone_for_skill(target_role, skill)
    if milestone:
        return "career_milestone"
    if _skill_key(skill) in {"aws", "docker", "kubernetes", "postgresql", "fastapi"}:
        return "certificate"
    return "skill"


def _build_skill_path_step(
    *,
    index: int,
    skill: str,
    state: dict[str, Any],
    q_value: float,
    policy_source: str,
) -> dict[str, Any]:
    target_role = str((state.get("user_profile") or {}).get("target_role") or "Data Scientist")
    components = _skill_path_reward_components(skill, state)
    action_index = _skill_index(skill)
    q_priority = _sigmoid(q_value)
    reward_priority = _clamp01(components["total_reward"] / 2.0)
    priority = _clamp01((0.85 * reward_priority) + (0.15 * q_priority))
    milestone = _milestone_for_skill(target_role, skill) or {}
    title = milestone.get("title") or f"Build {skill.title()} competency"
    return {
        "step_id": f"skill-{index + 1}",
        "skill": skill,
        "title": title,
        "action_type": _action_type_for_skill(target_role, skill),
        "priority": round(priority, 6),
        "q_value": round(float(q_value), 6),
        "action": action_index,
        "action_label": skill,
        "policy_source": policy_source,
        "policy_objective": "skill_path",
        "market_demand": round(float((state.get("market_demand") or {}).get(skill, 0.0)), 6),
        "reward_components": {
            key: value
            for key, value in components.items()
            if key != "estimated_skill_gap_after"
        },
        "skill_gap": round(float(state.get("skill_gap") or 0.0), 6),
        "estimated_skill_gap_after": components["estimated_skill_gap_after"],
        "missing_skills_before": list(state.get("missing_skills") or []),
        "milestone_id": milestone.get("milestone_id"),
        "required_skills": list(milestone.get("required_skills") or [skill]),
    }


def _fallback_skill_path_step(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": "skill-1",
        "skill": "portfolio",
        "title": "Maintain a portfolio of role-relevant work",
        "action_type": "career_milestone",
        "priority": 0.0,
        "q_value": 0.0,
        "action": None,
        "action_label": "portfolio",
        "policy_source": "mastery_maintenance",
        "policy_objective": "skill_path",
        "market_demand": 0.0,
        "reward_components": {
            "skill_gap_reduction": 0.0,
            "job_match_lift": 0.0,
            "total_reward": 0.0,
        },
        "skill_gap": round(float(state.get("skill_gap") or 0.0), 6),
        "estimated_skill_gap_after": round(float(state.get("skill_gap") or 0.0), 6),
        "missing_skills_before": list(state.get("missing_skills") or []),
        "milestone_id": None,
        "required_skills": [],
    }


def _rank_skill_path_steps(
    dqn_agent: OnlineDQN,
    *,
    user_id: int | str,
    state: dict[str, Any],
    candidate_skills: list[str] | None = None,
    max_steps: int = 8,
) -> list[dict[str, Any]]:
    missing_skills = list(state.get("missing_skills") or [])
    if candidate_skills:
        candidate_keys = {_skill_key(skill) for skill in candidate_skills}
        missing_skills = [skill for skill in missing_skills if _skill_key(skill) in candidate_keys]
    if not missing_skills:
        return [_fallback_skill_path_step(state)]

    profile = state.get("user_profile") or {}
    target_role = str(profile.get("target_role") or "Data Scientist")
    current_skills = list(profile.get("current_skills") or [])
    features_batch = [
        dqn_agent.featurize(
            str(user_id),
            {
                "id": f"skill:{_skill_key(skill)}",
                "title": f"{target_role} {skill}",
                "description": " ".join([target_role, skill, *current_skills]),
                "sbert_score": float((state.get("market_demand") or {}).get(skill, 0.5)),
                "ncf_score": 0.5,
            },
            {"interaction_count": len(current_skills), "skills": current_skills},
        )
        for skill in missing_skills
    ]
    q_matrix = dqn_agent.q_values_batch(np.asarray(features_batch, dtype=np.float32))
    candidates: list[dict[str, Any]] = []
    for skill, q_values in zip(missing_skills, q_matrix):
        action_index = _skill_index(skill)
        q_raw = float(q_values[action_index]) if len(q_values) > action_index else 0.0
        step = _build_skill_path_step(
            index=0,
            skill=skill,
            state=state,
            q_value=q_raw,
            policy_source="skill_path_policy",
        )
        components = step["reward_components"]
        step["_sort"] = (
            float(components["total_reward"]),
            float(step["market_demand"]),
            float(step["priority"]),
            skill.lower(),
        )
        candidates.append(step)
    candidates.sort(key=lambda item: item["_sort"], reverse=True)
    steps = []
    for index, step in enumerate(candidates[:max_steps]):
        step = {key: value for key, value in step.items() if key != "_sort"}
        step["step_id"] = f"skill-{index + 1}"
        steps.append(step)
    return steps


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "dqn",
        "model_version": MODEL_VERSION,
        "jobs": len(agent.jobs),
        "training_steps": agent.training_steps,
    }


@app.post("/jobs/upsert")
async def upsert_jobs(request: JobUpsertRequest) -> dict[str, Any]:
    count = agent.upsert_jobs(request.jobs)
    return {"status": "ok", "upserted": count, "jobs": len(agent.jobs)}


@app.post("/rank")
async def rank(request: RankRequest) -> dict[str, Any]:
    if not request.job_candidates:
        return {"user_id": str(request.user_id), "ranked": [], "reason": "no_candidates", "model_version": MODEL_VERSION}
    return {
        "user_id": str(request.user_id),
        "ranked": agent.rank(str(request.user_id), request.job_candidates, request.session_ctx),
        "model_version": MODEL_VERSION,
    }


@app.post("/learning-path")
async def learning_path(request: LearningPathRequest) -> dict[str, Any]:
    state = build_skill_path_state(
        user_id=request.user_id,
        current_skills=request.current_skills,
        target_role=request.target_role,
        market_demand=request.market_demand,
        profile_text=request.profile_text,
    )
    steps = _rank_skill_path_steps(
        agent,
        user_id=request.user_id,
        state=state,
        max_steps=request.max_steps,
    )

    return {
        "user_id": str(request.user_id),
        "target_role": request.target_role,
        "total_steps": len(steps),
        "learning_path": steps,
        "model_version": MODEL_VERSION,
        "policy_source": "skill_path_policy",
        "policy_objective": "skill_path",
        "mdp": {
            "state": state,
            "action_space": "next_skill_course_certificate_or_career_milestone",
            "reward": "skill_gap_reduction + job_match_lift",
        },
    }


@app.post("/rerank")
async def rerank(request: RerankRequest) -> dict[str, Any]:
    return {
        "user_id": str(request.user_id),
        "ranked": agent.rank(str(request.user_id), request.candidates, {"interaction_history": request.session_history}),
        "model_version": MODEL_VERSION,
    }


@app.post("/reward")
@app.post("/feedback")
async def update_reward(request: RewardUpdateRequest) -> dict[str, Any]:
    update = agent.learn(request)
    await _persist_replay(
        user_id=str(request.user_id),
        state=update.get("state", []),
        action=update.get("action", 0),
        reward=update.get("reward", 0.0),
        next_state=update.get("next_state", []),
        done=bool(request.done),
    )
    return {
        "status": "trained",
        "reward": reward_value(request.event, request.same_domain, request.reward),
        "training_steps": agent.training_steps,
        "replay_size": len(agent.replay),
        **{
            k: round(v, 6) if isinstance(v, (int, float)) else v
            for k, v in update.items()
        },
    }


@app.post("/recommend/dqn")
async def recommend_dqn(request: RecommendDQNRequest) -> dict[str, Any]:
    if request.state is not None:
        features = np.asarray(request.state, dtype=np.float32)
    else:
        job = request.job or {}
        features = agent.featurize(str(request.user_id), job, request.session_ctx)

    action_index, action_label, policy_source = agent._resolve_action(None, features)
    q_vals = agent.q_values(features)
    q_val = float(q_vals[action_index])

    return {
        "user_id": str(request.user_id),
        "action": action_index,
        "action_label": action_label,
        "q_value": round(q_val, 6),
        "policy_source": policy_source,
        "q_values": [round(float(v), 6) for v in q_vals],
        "model_version": MODEL_VERSION,
    }


@app.post("/feedback/dqn")
async def feedback_dqn(request: FeedbackDQNRequest) -> dict[str, Any]:
    update = agent.feedback(
        user_id=request.user_id,
        state=request.state,
        action=request.action,
        reward=request.reward,
        next_state=request.next_state,
        done=request.done,
        event=request.event,
    )
    await _persist_replay(
        user_id=str(request.user_id),
        state=request.state,
        action=update.get("action", 0),
        reward=update.get("reward", 0.0),
        next_state=request.next_state,
        done=request.done,
    )
    return {
        "status": "trained" if not update.get("wait_for_replay") else "buffering",
        "replay_size": len(agent.replay),
        "training_steps": agent.training_steps,
        **{
            k: round(v, 6) if isinstance(v, (int, float)) else v
            for k, v in update.items()
        },
    }


@app.post("/train")
async def train(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    batch_size = int(payload.get("batch_size", 16))
    loss = agent._train_from_replay(batch_size)
    samples = agent.replay.sample(batch_size)
    agent.soft_update()
    agent.save()
    return {
        "status": "ok",
        "sampled_experiences": len(samples),
        "loss": round(loss, 6),
        "soft_update_tau": 0.05,
        "model_version": MODEL_VERSION,
    }


@app.get("/model/status")
@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "service": "dqn",
        "model_version": MODEL_VERSION,
        "metrics": {
            "jobs": len(agent.jobs),
            "training_steps": agent.training_steps,
            "replay_size": len(agent.replay),
            "feature_dim": FEATURE_DIM,
            "learning_rate": LEARNING_RATE,
            "gamma": GAMMA,
            "last_trained_at": agent.last_trained_at,
        },
    }
