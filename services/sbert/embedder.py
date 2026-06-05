"""Deterministic fallback embedding and scoring for the SBERT service."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

import numpy as np

EMBEDDING_DIM = 384

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


def tokens(text: str) -> list[str]:
    raw = _TOKEN_RE.findall(text.lower())
    return [_INDONESIAN_NORMALISATION.get(token, token) for token in raw]


def category_scores(input_tokens: Iterable[str]) -> dict[str, float]:
    token_set = set(input_tokens)
    scores: dict[str, float] = {}
    for name, aliases in _ALIASES.items():
        overlap = token_set & aliases
        scores[name] = min(1.0, len(overlap) / 3.0)
    return scores


def _stable_noise(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    if dim <= 32:
        idx = int.from_bytes(digest[:2], "big") % max(1, dim)
    else:
        idx = 32 + int.from_bytes(digest[:2], "big") % (dim - 32)
    sign = 1.0 if digest[2] % 2 == 0 else -1.0
    return idx, sign * (0.08 + digest[3] / 2550.0)


def deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Create a normalized deterministic embedding without external weights."""
    input_tokens = tokens(text)
    vec = np.zeros(dim, dtype=np.float32)
    categories = category_scores(input_tokens)
    for idx, name in enumerate(_ALIASES):
        if idx < dim:
            vec[idx] = categories[name]

    token_set = set(input_tokens)
    for token in token_set:
        idx, value = _stable_noise(token, dim)
        vec[idx] += value

    empty_index = min(31, max(0, dim - 1))
    if not token_set:
        vec[empty_index] = 1.0

    norm = np.linalg.norm(vec)
    if norm == 0:
        vec[empty_index] = 1.0
        norm = 1.0
    return (vec / norm).astype(np.float32)


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denom)


def sbert_score(user_profile_text: str, job_description: str) -> float:
    """Deterministic semantic score in [0, 1] for tests and offline demos."""
    left_tokens = set(tokens(user_profile_text))
    right_tokens = set(tokens(job_description))
    if not left_tokens or not right_tokens:
        return 0.2

    left_categories = category_scores(left_tokens)
    right_categories = category_scores(right_tokens)
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
    embedding_score = (
        cosine(
            deterministic_embedding(user_profile_text),
            deterministic_embedding(job_description),
        )
        + 1.0
    ) / 2.0

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
