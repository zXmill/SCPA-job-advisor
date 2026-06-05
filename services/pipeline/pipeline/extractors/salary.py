"""Salary extraction and normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass


USD_TO_IDR = 16_000


@dataclass(frozen=True)
class SalaryResult:
    min_idr: int | None = None
    max_idr: int | None = None
    raw_currency: str | None = None
    raw_interval: str | None = None
    confidence: float = 0.0

    @property
    def has_value(self) -> bool:
        return self.min_idr is not None or self.max_idr is not None


def _parse_number(value: str, multiplier: int = 1) -> int:
    value = value.strip().lower().replace(",", "")
    if "." in value and not re.search(r"\.\d{1,2}$", value):
        value = value.replace(".", "")
    return int(float(value) * multiplier)


def _interval(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ("year", "tahun", "annum", "pa")):
        return "yearly"
    return "monthly"


def _monthly(value: int, currency: str, interval: str) -> int:
    if currency == "USD":
        value *= USD_TO_IDR
    if interval == "yearly":
        value = int(value / 12)
    return value


def extract_salary(
    text: str | None,
    *,
    hint_min: int | None = None,
    hint_max: int | None = None,
    hint_currency: str | None = None,
    hint_interval: str | None = None,
) -> SalaryResult:
    if hint_min is not None or hint_max is not None:
        return SalaryResult(
            min_idr=hint_min,
            max_idr=hint_max,
            raw_currency=(hint_currency or "IDR").upper(),
            raw_interval=hint_interval or "monthly",
            confidence=0.95,
        )
    if not text:
        return SalaryResult(confidence=0.0)
    lower = text.lower()
    if any(token in lower for token in ("negotiable", "kompetitif", "dirahasiakan")):
        return SalaryResult(confidence=0.1)

    interval = _interval(text)
    currency = "USD" if "usd" in lower or "$" in lower else "IDR"
    multiplier = 1
    if re.search(r"\b(juta|jt|million)\b", lower):
        multiplier = 1_000_000

    range_patterns = [
        r"(?:rp|idr)?\s*([\d][\d.,]*)\s*(?:juta|jt)?\s*[-–]\s*(?:rp|idr)?\s*([\d][\d.,]*)\s*(juta|jt)?",
        r"(?:usd|\$)\s*([\d][\d.,]*)\s*[-–]\s*(?:usd|\$)?\s*([\d][\d.,]*)",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, lower)
        if not match:
            continue
        inherited_multiplier = 1_000_000 if (match.lastindex or 0) >= 3 and match.group(3) in {"juta", "jt"} else multiplier
        left = _parse_number(match.group(1), inherited_multiplier)
        right = _parse_number(match.group(2), inherited_multiplier)
        return SalaryResult(
            min_idr=_monthly(min(left, right), currency, interval),
            max_idr=_monthly(max(left, right), currency, interval),
            raw_currency=currency,
            raw_interval=interval,
            confidence=0.85,
        )

    single = re.search(r"(?:rp|idr|usd|\$)?\s*([\d][\d.,]*)\s*(juta|jt)?", lower)
    if single:
        local_multiplier = 1_000_000 if single.group(2) in {"juta", "jt"} else multiplier
        value = _monthly(_parse_number(single.group(1), local_multiplier), currency, interval)
        return SalaryResult(
            min_idr=value,
            max_idr=value,
            raw_currency=currency,
            raw_interval=interval,
            confidence=0.65,
        )
    return SalaryResult(confidence=0.0)
