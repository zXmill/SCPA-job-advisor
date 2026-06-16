"""Real-model rankers for the SCPA thesis ablation.

This module drives the **actual deployed model classes** — ``OnlineNCF`` (NeuMF
+ MF) and ``OnlineDQN`` (Q-network session reranker) — over evaluation splits,
instead of the deterministic hash/smoke placeholders used by the earlier
``thesis_evaluation_protocol``. Each model is trained fresh on the *train*
split and evaluated on the held-out *test* split, the correct offline protocol.

Variants produced for the ablation:
- ``popularity``     : non-personalized global popularity (baseline floor).
- ``content``        : content/semantic affinity (SBERT-proxy candidate signal).
- ``ncf``            : real OnlineNCF collaborative scores.
- ``content_ncf``    : convex blend of content + NCF (hybrid without RL).
- ``full_scpa``      : content_ncf candidates re-ranked by the real OnlineDQN.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable

# The deployed model implementations. Importing also constructs module-level
# singletons that load deployed weights; we ignore those and train fresh
# instances so each evaluation reflects only its own train split.
from services.ncf.main import NCFRequest, OnlineNCF
from services.dqn.main import OnlineDQN, RewardUpdateRequest

Interaction = dict[str, Any]
Job = dict[str, Any]

#: Map a realized event to an NCF implicit-feedback target in [0, 1].
EVENT_TARGET = {
    "apply": 1.0,
    "save": 0.85,
    "click": 0.7,
    "view_10s": 0.6,
    "view": 0.2,
    "skip": 0.0,
    "immediate_skip": 0.0,
}


def event_target(event: str) -> float:
    return EVENT_TARGET.get(str(event).lower(), 0.2)


# --------------------------------------------------------------------------- #
# Non-personalized baselines
# --------------------------------------------------------------------------- #

def popularity_scores(train_rows: list[Interaction]) -> dict[str, int]:
    """Global positive-interaction count per job (popularity prior)."""
    counter: Counter[str] = Counter()
    for row in train_rows:
        if int(row.get("label") or 0) == 1:
            counter[str(row.get("job_id"))] += 1
    return dict(counter)


def rank_popularity(candidate_ids: list[str], popularity: dict[str, int]) -> list[str]:
    return sorted(candidate_ids, key=lambda jid: (-popularity.get(jid, 0), jid))


def rank_content(
    candidate_ids: list[str],
    content_score: dict[str, float],
) -> list[str]:
    """Rank candidates by a precomputed content/affinity score (SBERT proxy)."""
    return sorted(candidate_ids, key=lambda jid: (-content_score.get(jid, 0.0), jid))


# --------------------------------------------------------------------------- #
# NCF (real OnlineNCF)
# --------------------------------------------------------------------------- #

def train_ncf(
    train_rows: list[Interaction],
    *,
    profile_text_by_user: dict[str, str] | None = None,
    seed: int = 42,
) -> OnlineNCF:
    """Train a fresh OnlineNCF on the train split (no deployed-weight leakage)."""
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)

    model = OnlineNCF(autosave=False, load_existing=False)
    profile_text_by_user = profile_text_by_user or {}
    # Train in timestamp order so the online learner sees the same ordering it
    # would in production.
    for row in sorted(train_rows, key=lambda r: str(r.get("timestamp") or "")):
        user_id = str(row.get("user_id"))
        model.learn_one(
            user_id=user_id,
            job_id=str(row.get("job_id")),
            target=event_target(str(row.get("event"))),
            profile_text=profile_text_by_user.get(user_id),
        )
    return model


def ncf_scores(
    model: OnlineNCF,
    user_id: str,
    candidate_ids: list[str],
    *,
    profile_text: str | None = None,
) -> dict[str, float]:
    """Score a candidate pool for one user with the trained NCF."""
    if not candidate_ids:
        return {}
    recommendations = model.recommend(
        NCFRequest(
            user_id=user_id,
            n_items=min(len(candidate_ids), 1000),
            candidate_job_ids=list(candidate_ids),
            profile_text=profile_text,
        )
    )
    return {rec.job_id: float(rec.score) for rec in recommendations}


def rank_ncf(model: OnlineNCF, user_id: str, candidate_ids: list[str], *, profile_text: str | None = None) -> list[str]:
    scores = ncf_scores(model, user_id, candidate_ids, profile_text=profile_text)
    return sorted(candidate_ids, key=lambda jid: (-scores.get(jid, 0.0), jid))


def blend_scores(
    content_score: dict[str, float],
    ncf_score: dict[str, float],
    candidate_ids: list[str],
    *,
    w_content: float = 0.5,
    w_ncf: float = 0.5,
) -> dict[str, float]:
    """Convex blend of content and collaborative scores (hybrid, no RL)."""
    return {
        jid: (w_content * content_score.get(jid, 0.0)) + (w_ncf * ncf_score.get(jid, 0.0))
        for jid in candidate_ids
    }


# --------------------------------------------------------------------------- #
# DQN session reranker (real OnlineDQN)
# --------------------------------------------------------------------------- #

def train_dqn(
    train_sessions: list[dict[str, Any]],
    *,
    content_score: dict[str, float] | None = None,
    ncf_score: dict[str, float] | None = None,
    seed: int = 42,
) -> OnlineDQN:
    """Train a fresh OnlineDQN from session reward trajectories.

    Each session event becomes a reward transition; the last event in a session
    closes the episode (``done=True``). Candidate features carry the content
    (sbert) and NCF scores so the Q-network learns over the real signal blend.
    """
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    content_score = content_score or {}
    ncf_score = ncf_score or {}
    agent = OnlineDQN(autosave=False, load_existing=False)

    for session in sorted(train_sessions, key=lambda s: str(s.get("end_timestamp") or "")):
        user_id = str(session.get("user_id"))
        events = session.get("events") or []
        history: list[dict[str, Any]] = []
        for idx, event in enumerate(events):
            job_id = str(event.get("job_id"))
            job = {
                "id": job_id,
                "title": job_id,
                "sbert_score": content_score.get(job_id, float(event.get("affinity") or 0.0)),
                "ncf_score": ncf_score.get(job_id, 0.0),
            }
            is_last = idx == len(events) - 1
            agent.learn(
                RewardUpdateRequest(
                    user_id=user_id,
                    job_id=job_id,
                    event=str(event.get("event")),
                    job=job,
                    state={"interaction_history": list(history), "interaction_count": idx},
                    next_state={"interaction_history": history + [event], "interaction_count": idx + 1},
                    done=is_last,
                )
            )
            history.append(event)
    return agent


def rank_dqn(
    agent: OnlineDQN,
    user_id: str,
    candidate_ids: list[str],
    *,
    content_score: dict[str, float],
    ncf_score: dict[str, float],
    session_history: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Re-rank a candidate pool with the trained DQN session policy."""
    if not candidate_ids:
        return []
    jobs = [
        {
            "id": jid,
            "title": jid,
            "sbert_score": content_score.get(jid, 0.0),
            "base_score": content_score.get(jid, 0.0),
            "ncf_score": ncf_score.get(jid, 0.0),
        }
        for jid in candidate_ids
    ]
    ranked = agent.rank(
        user_id,
        jobs,
        {"interaction_history": session_history or [], "interaction_count": len(session_history or [])},
    )
    return [str(item["job_id"]) for item in ranked]


def session_reward(actions_or_events: list[Any], reward_fn: Callable[[str], float]) -> float:
    """Sum per-event reward over a session (for DQN reward-stability stats)."""
    total = 0.0
    for item in actions_or_events:
        event = item.get("event") if isinstance(item, dict) else item
        total += reward_fn(str(event))
    return total
