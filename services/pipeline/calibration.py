"""Learned calibration helpers for final recommendation ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import math
import re
from typing import Any, Mapping, Sequence


CALIBRATOR_MODE = "learned_logistic"
CALIBRATOR_MODEL_VERSION = "logistic_calibrator_synthetic_v1"
CALIBRATOR_BASELINE = "static_weighted_hybrid"
CALIBRATION_FEATURE_NAMES = (
    "static_score",
    "sbert_score",
    "ncf_score",
    "dqn_signal",
    "alignment_gap",
    "skill_alignment",
    "recency_score",
    "salary_score",
    "location_score",
    "interaction_depth",
)

_SALARY_RE = re.compile(r"\d+(?:[.,]\d+)?")
_REMOTE_TERMS = {"remote", "wfh", "hybrid"}
_INDONESIA_TERMS = {
    "indonesia",
    "jakarta",
    "bandung",
    "surabaya",
    "yogyakarta",
    "jogja",
    "bali",
    "semarang",
    "medan",
    "makassar",
}


@dataclass(frozen=True)
class LogisticCalibrationModel:
    """Small logistic ranker trained on a deterministic calibration smoke set."""

    weights: dict[str, float]
    bias: float
    feature_names: tuple[str, ...] = CALIBRATION_FEATURE_NAMES
    mode: str = CALIBRATOR_MODE
    model_version: str = CALIBRATOR_MODEL_VERSION
    training_source: str = "synthetic_calibration_smoke_v1"

    def predict_probability(self, features: Mapping[str, float]) -> float:
        logit = self.bias + sum(
            self.weights.get(name, 0.0) * float(features.get(name, 0.0))
            for name in self.feature_names
        )
        return _sigmoid(logit)

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "baseline": CALIBRATOR_BASELINE,
            "model_version": self.model_version,
            "training_source": self.training_source,
            "feature_names": list(self.feature_names),
            "score_blend": {"logistic_probability": 0.85, "static_baseline": 0.15},
        }


def _clamp01(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def recency_score(value: Any, *, now: datetime | None = None) -> float:
    posted_at = _parse_datetime(value)
    if posted_at is None:
        return 0.5
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now.astimezone(timezone.utc) - posted_at).total_seconds() / 86400.0)
    return _clamp01(1.0 - (age_days / 90.0))


def _parse_salary_text(text: Any) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    raw = str(text).lower()
    values = [float(match.group(0).replace(",", ".")) for match in _SALARY_RE.finditer(raw)]
    if not values:
        return None, None
    multiplier = 1.0
    if "juta" in raw or "jt" in raw:
        multiplier = 1_000_000.0
    elif "ribu" in raw:
        multiplier = 1_000.0
    normalized = [value * multiplier for value in values]
    if multiplier == 1.0 and max(normalized) < 100_000:
        normalized = [value * 1_000_000.0 for value in normalized]
    return min(normalized), max(normalized)


def salary_score(user: Mapping[str, Any], job: Mapping[str, Any]) -> float:
    min_salary = _as_float(job.get("min_salary") or job.get("salary_min"))
    max_salary = _as_float(job.get("max_salary") or job.get("salary_max"))
    if min_salary is None and max_salary is None:
        min_salary, max_salary = _parse_salary_text(job.get("salary_text"))
    if min_salary is None and max_salary is None:
        return 0.5
    salary = max_salary or min_salary or 0.0
    if min_salary is not None and max_salary is not None:
        salary = (min_salary + max_salary) / 2.0
    expected = (
        _as_float(user.get("expected_salary_min"))
        or _as_float(user.get("salary_expectation_min"))
        or _as_float(user.get("min_salary"))
    )
    if expected and expected > 0:
        if salary >= expected:
            return _clamp01(0.7 + (0.3 * min(salary / (expected * 2.0), 1.0)))
        return _clamp01(0.7 * (salary / expected))
    return _clamp01(salary / 30_000_000.0)


def location_score(user: Mapping[str, Any], job: Mapping[str, Any]) -> float:
    job_location = str(job.get("location") or "").strip().lower()
    if not job_location:
        return 0.5
    if any(term in job_location for term in _REMOTE_TERMS):
        return 1.0
    preferred_locations = [
        *(_as_text_list(user.get("preferred_locations"))),
        *(_as_text_list(user.get("location"))),
    ]
    preferred = [item.lower() for item in preferred_locations if item]
    if not preferred:
        return 0.5
    if any(location and location in job_location for location in preferred):
        return 1.0
    if (set(job_location.replace(",", " ").split()) & _INDONESIA_TERMS) and any(
        location in _INDONESIA_TERMS or "indonesia" in location for location in preferred
    ):
        return 0.75
    return 0.2


def interaction_depth(user: Mapping[str, Any]) -> float:
    count = _as_float(user.get("interaction_count")) or 0.0
    return _clamp01(count / 50.0)


def extract_calibration_features(
    user: Mapping[str, Any],
    job: Mapping[str, Any],
    *,
    static_score: float,
    alignment_score: float,
    now: datetime | None = None,
) -> dict[str, float]:
    alignment_gap = _as_float(job.get("alignment_gap"))
    if alignment_gap is None:
        alignment_gap = 1.0 - alignment_score
    features = {
        "static_score": _clamp01(float(static_score)),
        "sbert_score": _clamp01(float(job.get("sbert_score") or 0.0)),
        "ncf_score": _clamp01(float(job.get("ncf_score") or 0.0)),
        "dqn_signal": _clamp01(float(job.get("dqn_score") or 0.0)),
        "alignment_gap": _clamp01(float(alignment_gap)),
        "skill_alignment": _clamp01(float(alignment_score)),
        "recency_score": recency_score(job.get("posted_at") or job.get("created_at"), now=now),
        "salary_score": salary_score(user, job),
        "location_score": location_score(user, job),
        "interaction_depth": interaction_depth(user),
    }
    return {name: round(features[name], 6) for name in CALIBRATION_FEATURE_NAMES}


def fit_logistic_calibrator(
    examples: Sequence[tuple[Mapping[str, float], float]],
    *,
    epochs: int = 900,
    learning_rate: float = 0.45,
    l2: float = 0.01,
) -> LogisticCalibrationModel:
    weights = {name: 0.0 for name in CALIBRATION_FEATURE_NAMES}
    bias = 0.0
    n_examples = max(1, len(examples))
    for _ in range(epochs):
        grad_w = {name: 0.0 for name in CALIBRATION_FEATURE_NAMES}
        grad_b = 0.0
        for features, label in examples:
            prediction = _sigmoid(
                bias
                + sum(weights[name] * float(features.get(name, 0.0)) for name in CALIBRATION_FEATURE_NAMES)
            )
            error = prediction - float(label)
            grad_b += error
            for name in CALIBRATION_FEATURE_NAMES:
                grad_w[name] += error * float(features.get(name, 0.0))
        bias -= learning_rate * (grad_b / n_examples)
        for name in CALIBRATION_FEATURE_NAMES:
            regularized = (grad_w[name] / n_examples) + (l2 * weights[name])
            weights[name] -= learning_rate * regularized
    return LogisticCalibrationModel(
        weights={name: round(value, 8) for name, value in weights.items()},
        bias=round(bias, 8),
    )


def synthetic_calibration_examples() -> list[tuple[dict[str, float], float]]:
    """Return a small deterministic fixture, not production training data."""
    return [
        (
            {
                "static_score": 0.49,
                "sbert_score": 0.86,
                "ncf_score": 0.18,
                "dqn_signal": 0.12,
                "alignment_gap": 0.75,
                "skill_alignment": 0.25,
                "recency_score": 0.0,
                "salary_score": 0.2,
                "location_score": 0.2,
                "interaction_depth": 0.7,
            },
            0.0,
        ),
        (
            {
                "static_score": 0.48,
                "sbert_score": 0.62,
                "ncf_score": 0.62,
                "dqn_signal": 0.72,
                "alignment_gap": 0.08,
                "skill_alignment": 0.75,
                "recency_score": 0.95,
                "salary_score": 0.95,
                "location_score": 1.0,
                "interaction_depth": 0.7,
            },
            1.0,
        ),
        (
            {
                "static_score": 0.72,
                "sbert_score": 0.78,
                "ncf_score": 0.68,
                "dqn_signal": 0.70,
                "alignment_gap": 0.12,
                "skill_alignment": 0.9,
                "recency_score": 0.85,
                "salary_score": 0.8,
                "location_score": 0.75,
                "interaction_depth": 0.4,
            },
            1.0,
        ),
        (
            {
                "static_score": 0.58,
                "sbert_score": 0.80,
                "ncf_score": 0.32,
                "dqn_signal": 0.20,
                "alignment_gap": 0.85,
                "skill_alignment": 0.1,
                "recency_score": 0.3,
                "salary_score": 0.35,
                "location_score": 0.2,
                "interaction_depth": 0.4,
            },
            0.0,
        ),
        (
            {
                "static_score": 0.66,
                "sbert_score": 0.55,
                "ncf_score": 0.76,
                "dqn_signal": 0.74,
                "alignment_gap": 0.18,
                "skill_alignment": 0.65,
                "recency_score": 0.7,
                "salary_score": 0.9,
                "location_score": 1.0,
                "interaction_depth": 1.0,
            },
            1.0,
        ),
        (
            {
                "static_score": 0.40,
                "sbert_score": 0.42,
                "ncf_score": 0.25,
                "dqn_signal": 0.22,
                "alignment_gap": 0.7,
                "skill_alignment": 0.15,
                "recency_score": 0.1,
                "salary_score": 0.3,
                "location_score": 0.2,
                "interaction_depth": 1.0,
            },
            0.0,
        ),
    ]


@lru_cache(maxsize=1)
def get_default_calibrator() -> LogisticCalibrationModel:
    return fit_logistic_calibrator(synthetic_calibration_examples())


def calibrated_score(features: Mapping[str, float], model: LogisticCalibrationModel | None = None) -> float:
    model = model or get_default_calibrator()
    probability = model.predict_probability(features)
    static_score = float(features.get("static_score", 0.0))
    return _clamp01((0.85 * probability) + (0.15 * static_score))
