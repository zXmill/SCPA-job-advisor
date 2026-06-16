"""Grounded behavioral benchmark generator for SCPA thesis evaluation.

The behavioral models (NCF personalization, DQN session rerank) need a
user x job interaction log with timestamps and sessions. Real runtime feedback
exists only as a tiny "readiness" smoke set, far below thesis-evidence
thresholds. To produce a *strong, reproducible, and honestly disclosed*
offline benchmark, this module simulates interactions whose ground-truth
preference is derived from **real** profile/job attributes (domain,
occupation_group, skill overlap) drawn from the fine-tuning corpus.

Provenance is always stamped ``simulated_grounded`` so no downstream artifact
can present these numbers as real-user evidence. The generative model and its
parameters are emitted alongside the data so the simulation is fully auditable
and defensible at a thesis defense (a standard offline-evaluation practice in
RecSys / RL when production interaction logs are not yet available).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# --- Documented generative parameters (auditable; emitted with the data) ----

#: Weight of skill Jaccard overlap in the affinity score.
W_SKILL = 0.45
#: Weight of exact domain match in the affinity score.
W_DOMAIN = 0.35
#: Weight of exact occupation-group match in the affinity score.
W_OCCUPATION = 0.20

#: Logistic steepness of the engagement (click) model.
ENGAGE_SCALE = 6.0
#: Affinity midpoint where engagement probability crosses 0.5.
ENGAGE_MIDPOINT = 0.45
#: Per-event logistic noise (std of an additive Gaussian on the logit).
ENGAGE_NOISE = 0.6

#: Graded relevance grade by realized event (used for NDCG gold gains).
EVENT_RELEVANCE_GRADE = {
    "apply": 3.0,
    "save": 2.0,
    "click": 1.0,
    "view_10s": 1.0,
    "view": 0.0,
    "skip": 0.0,
    "immediate_skip": 0.0,
}
#: Events counted as a positive (relevant) interaction for binary metrics.
POSITIVE_EVENTS = frozenset({"apply", "save", "click", "view_10s"})

GENERATIVE_PARAMS = {
    "affinity_weights": {"skill": W_SKILL, "domain": W_DOMAIN, "occupation": W_OCCUPATION},
    "engagement_model": "logistic(sigmoid(scale*(affinity-midpoint)+noise))",
    "engage_scale": ENGAGE_SCALE,
    "engage_midpoint": ENGAGE_MIDPOINT,
    "engage_noise_std": ENGAGE_NOISE,
    "event_relevance_grade": EVENT_RELEVANCE_GRADE,
    "positive_events": sorted(POSITIVE_EVENTS),
    "grounding": "real profile/job domain, occupation_group, and skill attributes",
}


@dataclass(frozen=True)
class Interaction:
    """One simulated user-job interaction event."""

    user_id: str
    job_id: str
    session_id: str
    event: str
    label: int
    relevance_grade: float
    affinity: float
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "job_id": self.job_id,
            "session_id": self.session_id,
            "event": self.event,
            "label": self.label,
            "relevance_grade": self.relevance_grade,
            "affinity": round(self.affinity, 6),
            "timestamp": self.timestamp,
            "provenance": "simulated_grounded",
        }


@dataclass(frozen=True)
class BehaviorBenchmark:
    """A generated benchmark: interactions, sessions, and audit metadata."""

    interactions: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    users: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


def _norm_token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _skill_set(*values: Any) -> set[str]:
    out: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            out |= {_norm_token(item) for item in value if str(item).strip()}
        elif isinstance(value, str) and value.strip():
            out |= {_norm_token(tok) for tok in value.replace(",", " ").split() if tok.strip()}
    return {tok for tok in out if tok}


def compute_affinity(profile: dict[str, Any], job: dict[str, Any]) -> float:
    """Ground-truth preference in [0, 1] from real profile/job attributes.

    Combines skill Jaccard overlap, exact domain match, and exact
    occupation-group match. Deterministic — no randomness here so the
    affinity is a pure, auditable function of the corpus attributes.
    """
    profile_skills = _skill_set(profile.get("skills"))
    job_skills = _skill_set(job.get("required_skills"), job.get("preferred_skills"), job.get("skills"))
    if profile_skills or job_skills:
        union = profile_skills | job_skills
        jaccard = len(profile_skills & job_skills) / len(union) if union else 0.0
    else:
        jaccard = 0.0

    domain_match = 1.0 if _norm_token(profile.get("domain")) and _norm_token(profile.get("domain")) == _norm_token(job.get("domain")) else 0.0
    occ_match = 1.0 if _norm_token(profile.get("occupation_group")) and _norm_token(profile.get("occupation_group")) == _norm_token(job.get("occupation_group")) else 0.0

    affinity = (W_SKILL * jaccard) + (W_DOMAIN * domain_match) + (W_OCCUPATION * occ_match)
    return float(max(0.0, min(1.0, affinity)))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def _sample_event(affinity: float, rng: random.Random) -> tuple[str, int, float]:
    """Sample a realized event from the grounded click model.

    Returns (event, binary_label, relevance_grade).
    """
    logit = ENGAGE_SCALE * (affinity - ENGAGE_MIDPOINT) + rng.gauss(0.0, ENGAGE_NOISE)
    p_engage = _sigmoid(logit)
    if rng.random() < p_engage:
        # Positive engagement; stronger affinity skews toward stronger events.
        roll = rng.random()
        if affinity >= 0.6 and roll < 0.45:
            event = "apply"
        elif affinity >= 0.4 and roll < 0.55:
            event = "save"
        elif roll < 0.75:
            event = "click"
        else:
            event = "view_10s"
        return event, 1, EVENT_RELEVANCE_GRADE[event]
    # Negative / non-engagement.
    event = "skip" if affinity < 0.25 else "view"
    return event, 0, EVENT_RELEVANCE_GRADE[event]


def _candidate_pool(
    profile: dict[str, Any],
    jobs: list[dict[str, Any]],
    pool_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Build a per-user candidate pool: relevant (same-domain) jobs + noise.

    Mixing matched and random jobs gives every user both positive signal and
    realistic negatives, so the ranking task is non-trivial.
    """
    domain = _norm_token(profile.get("domain"))
    occ = _norm_token(profile.get("occupation_group"))
    matched = [j for j in jobs if _norm_token(j.get("domain")) == domain or _norm_token(j.get("occupation_group")) == occ]
    rng.shuffle(matched)
    n_matched = min(len(matched), max(1, pool_size // 2))
    pool = matched[:n_matched]
    remaining = [j for j in jobs if j not in pool]
    rng.shuffle(remaining)
    pool += remaining[: max(0, pool_size - len(pool))]
    rng.shuffle(pool)
    return pool[:pool_size]


def generate_behavior_benchmark(
    profiles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    *,
    n_users: int = 300,
    candidate_pool_size: int = 60,
    sessions_per_user: int = 3,
    seed: int = 42,
    base_time: datetime | None = None,
) -> BehaviorBenchmark:
    """Generate a grounded, reproducible behavioral benchmark.

    Each user is a real profile; each candidate job is a real job. Interactions
    are sampled from the documented click model over the real-attribute
    affinity. Session timestamps are scheduled as interleaved user waves, so a
    temporal split represents returning users over time instead of a batch of
    early users followed by a batch of late users. ``session_id`` groups events
    for session-level (DQN) splits.
    """
    rng = random.Random(seed)
    base_time = base_time or datetime(2026, 1, 1, tzinfo=timezone.utc)

    chosen_profiles = profiles[:n_users] if len(profiles) >= n_users else list(profiles)
    interactions: list[Interaction] = []
    sessions: list[dict[str, Any]] = []
    used_user_records: list[dict[str, Any]] = []
    used_job_ids: set[str] = set()

    # Separate schedule RNG keeps the temporal interleaving deterministic
    # without changing the click/no-click sampling sequence.
    schedule_rng = random.Random(seed + 1009)
    user_count = len(chosen_profiles)
    wave_order_by_user: list[dict[int, int]] = []
    for _ in range(sessions_per_user):
        order = list(range(user_count))
        schedule_rng.shuffle(order)
        wave_order_by_user.append({user_index: slot for slot, user_index in enumerate(order)})

    for u_index, profile in enumerate(chosen_profiles):
        user_id = str(profile.get("profile_id") or f"sim-user-{u_index:05d}")
        used_user_records.append({
            "user_id": user_id,
            "domain": profile.get("domain"),
            "occupation_group": profile.get("occupation_group"),
            "skills": profile.get("skills"),
            "profile_text": profile.get("profile_text"),
        })
        pool = _candidate_pool(profile, jobs, candidate_pool_size, rng)
        per_session = max(1, len(pool) // sessions_per_user)
        for s_index in range(sessions_per_user):
            session_id = f"{user_id}-s{s_index}"
            session_jobs = pool[s_index * per_session : (s_index + 1) * per_session]
            if not session_jobs:
                continue
            schedule_slot = (s_index * user_count) + wave_order_by_user[s_index][u_index]
            clock = base_time + timedelta(hours=3 * schedule_slot, seconds=schedule_rng.randint(0, 120))
            session_events: list[dict[str, Any]] = []
            session_interactions: list[Interaction] = []
            session_reward = 0.0
            for job in session_jobs:
                job_id = str(job.get("job_id") or job.get("id"))
                used_job_ids.add(job_id)
                affinity = compute_affinity(profile, job)
                event, label, grade = _sample_event(affinity, rng)
                clock = clock + timedelta(seconds=rng.randint(20, 240))
                inter = Interaction(
                    user_id=user_id,
                    job_id=job_id,
                    session_id=session_id,
                    event=event,
                    label=label,
                    relevance_grade=grade,
                    affinity=affinity,
                    timestamp=clock.isoformat(),
                )
                interactions.append(inter)
                session_interactions.append(inter)
                session_events.append({"job_id": job_id, "event": event, "affinity": round(affinity, 4)})
                session_reward += grade
            sessions.append({
                "session_id": session_id,
                "user_id": user_id,
                "events": session_events,
                "session_reward": round(session_reward, 4),
                "start_timestamp": session_interactions[0].timestamp if session_interactions else clock.isoformat(),
                "end_timestamp": session_interactions[-1].timestamp if session_interactions else clock.isoformat(),
                "provenance": "simulated_grounded",
            })

    job_by_id = {str(j.get("job_id") or j.get("id")): j for j in jobs}
    used_jobs = [
        {
            "job_id": jid,
            "title": job_by_id.get(jid, {}).get("title"),
            "domain": job_by_id.get(jid, {}).get("domain"),
            "occupation_group": job_by_id.get(jid, {}).get("occupation_group"),
            "required_skills": job_by_id.get(jid, {}).get("required_skills"),
            "preferred_skills": job_by_id.get(jid, {}).get("preferred_skills"),
        }
        for jid in sorted(used_job_ids)
    ]

    interactions = sorted(interactions, key=lambda i: i.timestamp)
    sessions = sorted(sessions, key=lambda s: str(s.get("end_timestamp") or ""))
    interaction_dicts = [i.as_dict() for i in interactions]
    positives = sum(1 for i in interaction_dicts if i["label"] == 1)
    metadata = {
        "provenance": "simulated_grounded",
        "disclosure": (
            "Interactions are SIMULATED from a documented click model whose "
            "ground-truth preference is derived from REAL profile/job domain, "
            "occupation_group, and skill attributes. Numbers are offline "
            "simulation evidence, NOT real-user evidence, and must be disclosed "
            "as such in Bab IV."
        ),
        "seed": seed,
        "n_users": len(used_user_records),
        "n_jobs": len(used_jobs),
        "n_interactions": len(interaction_dicts),
        "n_positive_interactions": positives,
        "positive_rate": round(positives / len(interaction_dicts), 4) if interaction_dicts else 0.0,
        "n_sessions": len(sessions),
        "candidate_pool_size": candidate_pool_size,
        "sessions_per_user": sessions_per_user,
        "temporal_schedule": "interleaved_user_waves",
        "temporal_schedule_disclosure": (
            "Sessions are scheduled as cross-user waves; later temporal windows "
            "therefore evaluate returning users with earlier train history, not "
            "only new users introduced late by generator order."
        ),
        "generative_params": GENERATIVE_PARAMS,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return BehaviorBenchmark(
        interactions=interaction_dicts,
        sessions=sessions,
        users=used_user_records,
        jobs=used_jobs,
        metadata=metadata,
    )


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    import json

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_benchmark(benchmark: BehaviorBenchmark, out_dir: Path) -> dict[str, str]:
    """Persist the generated benchmark as durable JSONL/JSON evidence files."""
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "interactions": out_dir / "interactions.jsonl",
        "sessions": out_dir / "sessions.jsonl",
        "metadata": out_dir / "benchmark_metadata.json",
    }
    with paths["interactions"].open("w", encoding="utf-8") as handle:
        for row in benchmark.interactions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with paths["sessions"].open("w", encoding="utf-8") as handle:
        for row in benchmark.sessions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    paths["metadata"].write_text(json.dumps(benchmark.metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}
