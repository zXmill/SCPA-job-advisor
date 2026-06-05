"""Deterministic hard-negative mining for SBERT training data."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Callable

ScoreFn = Callable[[str, str], float]

EMBEDDING_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")

_SKILL_ALIASES: dict[str, set[str]] = {
    "api": {"api", "rest", "endpoint", "microservice", "backend"},
    "cloud": {"aws", "cloud", "docker", "kubernetes", "devops", "deployment"},
    "communication": {"communication", "komunikasi", "presentation", "public", "speaking"},
    "content": {"content", "copywriting", "writing", "writer", "caption"},
    "data_analysis": {"analytics", "analyst", "dashboard", "statistics", "tableau"},
    "design": {"design", "designer", "figma", "prototype", "ui", "ux"},
    "frontend": {"css", "frontend", "javascript", "next.js", "react", "typescript"},
    "machine_learning": {"ai", "learning", "machine", "ml", "model", "pytorch", "tensorflow"},
    "python": {"django", "fastapi", "flask", "python"},
    "sql": {"database", "postgres", "postgresql", "sql"},
}

_SKILL_SECTORS: dict[str, str] = {
    "api": "technology",
    "cloud": "technology",
    "data_analysis": "technology",
    "design": "technology",
    "frontend": "technology",
    "machine_learning": "technology",
    "python": "technology",
    "sql": "technology",
    "communication": "communications",
    "content": "communications",
}

_ANCHOR_FIELDS = ("query", "title", "profile", "profile_text", "anchor", "user_profile_text")
_POSITIVE_FIELDS = ("positive", "description", "job_description", "job_text")
_NEGATIVE_FIELDS = ("negative", "hard_negative", "negative_job_description")
_SECTOR_FIELDS = ("sector", "job_sector", "category", "domain")
_SKILL_FIELDS = ("skills", "required_skills", "positive_skills", "job_skills")


@dataclass(frozen=True)
class TrainingItem:
    """Normalized source row used for deterministic mining."""

    source_id: str
    anchor: str
    positive: str
    sector: str
    skills: tuple[str, ...]
    explicit_negative: str | None = None


@dataclass(frozen=True)
class HardNegativeExample:
    """One SBERT training contract row with a same-sector wrong-skill negative."""

    source_id: str
    negative_source_id: str
    anchor: str
    positive: str
    hard_negative: str
    sector: str
    positive_skills: tuple[str, ...]
    negative_skills: tuple[str, ...]
    positive_score: float
    negative_score: float
    margin: float

    def to_training_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["positive_skills"] = list(self.positive_skills)
        row["negative_skills"] = list(self.negative_skills)
        return row


def deterministic_training_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Create a stable lightweight embedding for offline training smoke tests."""

    import math

    vec = [0.0] * dim
    skills = infer_skills(text)
    for skill in skills:
        idx = _stable_index(f"skill:{skill}", dim)
        vec[idx] += 0.8
    for token in set(normalize_tokens(text)):
        idx = _stable_index(f"token:{token}", dim)
        vec[idx] += 0.2

    if not skills and not normalize_tokens(text):
        vec[0] = 1.0

    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def default_similarity_score(anchor: str, job_text: str) -> float:
    """Deterministic training-data scorer for positive-over-negative contracts."""

    import math

    anchor_tokens = set(normalize_tokens(anchor))
    job_tokens = set(normalize_tokens(job_text))
    if not anchor_tokens or not job_tokens:
        return 0.0

    anchor_skills = set(infer_skills(anchor))
    job_skills = set(infer_skills(job_text))
    skill_overlap = len(anchor_skills & job_skills) / max(1, len(anchor_skills | job_skills))
    lexical_overlap = len(anchor_tokens & job_tokens) / math.sqrt(len(anchor_tokens) * len(job_tokens))
    sector_bonus = 0.1 if infer_sector(anchor_skills, anchor) == infer_sector(job_skills, job_text) else 0.0

    score = 0.15 + 0.65 * skill_overlap + 0.20 * lexical_overlap + sector_bonus
    return round(min(1.0, max(0.0, score)), 6)


def normalize_tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(text.lower()))


def infer_skills(*texts: str, explicit_skills: Iterable[str] = ()) -> tuple[str, ...]:
    tokens = set()
    for text in texts:
        tokens.update(normalize_tokens(text))

    skills = {str(skill).strip().lower().replace(" ", "_") for skill in explicit_skills if str(skill).strip()}
    for skill, aliases in _SKILL_ALIASES.items():
        if tokens & aliases:
            skills.add(skill)
    return tuple(sorted(skills))


def infer_sector(skills: Iterable[str], fallback_text: str = "") -> str:
    counts: dict[str, int] = {}
    for skill in skills:
        sector = _SKILL_SECTORS.get(skill)
        if sector:
            counts[sector] = counts.get(sector, 0) + 1
    if counts:
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    tokens = set(normalize_tokens(fallback_text))
    if tokens & {"sales", "marketing", "customer", "business"}:
        return "business"
    return "general"


def normalize_sector(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "general"


def extract_training_items(records: list[dict[str, Any]]) -> list[TrainingItem]:
    items: list[TrainingItem] = []
    for index, record in enumerate(records):
        anchor = _first_text(record, _ANCHOR_FIELDS)
        positive = _first_text(record, _POSITIVE_FIELDS)
        if not anchor or not positive:
            continue

        explicit_skills = _flatten_skills(record, _SKILL_FIELDS)
        skills = infer_skills(anchor, positive, explicit_skills=explicit_skills)
        explicit_sector = _first_text(record, _SECTOR_FIELDS)
        sector = normalize_sector(explicit_sector) if explicit_sector else infer_sector(skills, f"{anchor} {positive}")
        source_id = _source_id(record, index, anchor, positive)

        items.append(
            TrainingItem(
                source_id=source_id,
                anchor=anchor,
                positive=positive,
                sector=sector,
                skills=skills,
                explicit_negative=_first_text(record, _NEGATIVE_FIELDS) or None,
            )
        )

    return sorted(items, key=lambda item: item.source_id)


def mine_hard_negative_examples(
    records: list[dict[str, Any]],
    *,
    scorer: ScoreFn = default_similarity_score,
    max_skill_overlap: float = 0.25,
    min_margin: float = 0.0,
    allow_explicit_fallback: bool = False,
) -> list[HardNegativeExample]:
    """Mine deterministic same-sector wrong-skill hard negatives.

    Candidate negatives come from another positive job in the same sector. They
    must have low skill overlap and must score below the aligned positive pair.
    Explicit negatives are used only when ``allow_explicit_fallback`` is set,
    because the thesis contract asks for same-sector wrong-skill negatives.
    """

    items = extract_training_items(records)
    examples: list[HardNegativeExample] = []

    for item in items:
        positive_score = float(scorer(item.anchor, item.positive))
        candidates: list[tuple[float, TrainingItem]] = []
        for candidate in items:
            if candidate.source_id == item.source_id:
                continue
            if candidate.sector != item.sector:
                continue
            if not _is_wrong_skill_match(item.skills, candidate.skills, max_skill_overlap):
                continue
            negative_score = float(scorer(item.anchor, candidate.positive))
            if positive_score <= negative_score + min_margin:
                continue
            candidates.append((negative_score, candidate))

        if candidates:
            negative_score, negative_item = sorted(
                candidates,
                key=lambda entry: (-entry[0], entry[1].source_id),
            )[0]
            examples.append(
                _build_example(
                    item=item,
                    negative_source_id=negative_item.source_id,
                    hard_negative=negative_item.positive,
                    negative_skills=negative_item.skills,
                    positive_score=positive_score,
                    negative_score=negative_score,
                )
            )
            continue

        if allow_explicit_fallback and item.explicit_negative:
            negative_score = float(scorer(item.anchor, item.explicit_negative))
            if positive_score > negative_score + min_margin:
                examples.append(
                    _build_example(
                        item=item,
                        negative_source_id=f"{item.source_id}:explicit-negative",
                        hard_negative=item.explicit_negative,
                        negative_skills=infer_skills(item.explicit_negative),
                        positive_score=positive_score,
                        negative_score=negative_score,
                    )
                )

    return examples


def validate_positive_outranks_negatives(
    examples: Iterable[HardNegativeExample],
    *,
    min_margin: float = 0.0,
) -> dict[str, float | int]:
    examples_list = list(examples)
    if not examples_list:
        return {
            "hard_negative_pairs": 0,
            "positive_outrank_rate": 0.0,
            "mean_hard_negative_margin": 0.0,
            "ranking_violations": 0,
        }

    margins = [example.margin for example in examples_list]
    violations = sum(1 for margin in margins if margin <= min_margin)
    return {
        "hard_negative_pairs": len(examples_list),
        "positive_outrank_rate": round((len(examples_list) - violations) / len(examples_list), 6),
        "mean_hard_negative_margin": round(sum(margins) / len(margins), 6),
        "ranking_violations": violations,
    }


def assert_positive_outranks_negatives(
    examples: Iterable[HardNegativeExample],
    *,
    min_margin: float = 0.0,
) -> dict[str, float | int]:
    metrics = validate_positive_outranks_negatives(examples, min_margin=min_margin)
    if metrics["ranking_violations"]:
        raise ValueError("positive SBERT pairs must outrank mined hard negatives")
    return metrics


def _build_example(
    *,
    item: TrainingItem,
    negative_source_id: str,
    hard_negative: str,
    negative_skills: tuple[str, ...],
    positive_score: float,
    negative_score: float,
) -> HardNegativeExample:
    margin = round(positive_score - negative_score, 6)
    return HardNegativeExample(
        source_id=item.source_id,
        negative_source_id=negative_source_id,
        anchor=item.anchor,
        positive=item.positive,
        hard_negative=hard_negative,
        sector=item.sector,
        positive_skills=item.skills,
        negative_skills=negative_skills,
        positive_score=round(positive_score, 6),
        negative_score=round(negative_score, 6),
        margin=margin,
    )


def _is_wrong_skill_match(
    positive_skills: tuple[str, ...],
    negative_skills: tuple[str, ...],
    max_skill_overlap: float,
) -> bool:
    if not positive_skills or not negative_skills:
        return False
    positive_set = set(positive_skills)
    negative_set = set(negative_skills)
    overlap = positive_set & negative_set
    overlap_ratio = len(overlap) / max(1, min(len(positive_set), len(negative_set)))
    return overlap_ratio <= max_skill_overlap


def _stable_index(value: str, dim: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % dim


def _first_text(record: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = record.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _flatten_skills(record: dict[str, Any], names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for name in names:
        raw = record.get(name)
        if raw is None:
            continue
        if isinstance(raw, str):
            values.extend(part.strip() for part in re.split(r"[,;/|]", raw) if part.strip())
        elif isinstance(raw, Iterable):
            values.extend(str(part).strip() for part in raw if str(part).strip())
    return values


def _source_id(record: dict[str, Any], _index: int, anchor: str, positive: str) -> str:
    for field in ("id", "job_id", "source_id"):
        value = record.get(field)
        if value is not None and str(value).strip():
            return normalize_sector(value)
    digest = hashlib.sha256(f"{anchor}\n{positive}".encode("utf-8")).hexdigest()[:12]
    return f"record_{digest}"
