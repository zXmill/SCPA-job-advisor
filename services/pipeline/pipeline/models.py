"""Structured job models used by the pipeline normalizer."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_SPACE_RE = re.compile(r"\s+")


def _clean(value: str | None) -> str:
    return _SPACE_RE.sub(" ", value or "").strip()


def build_dedupe_key(title: str, company: str, location: str | None = None) -> str:
    raw = "|".join(
        part.lower()
        for part in (_clean(title), _clean(company), _clean(location))
        if part
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_url_hash(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    parsed = urlsplit(url.strip())
    normalized = urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class RawJobPosting:
    title: str
    company: str
    source: str
    location: str | None = None
    description: str | None = None
    description_html: str | None = None
    salary_text: str | None = None
    apply_url: str | None = None
    company_logo: str | None = None
    min_salary_hint: int | None = None
    max_salary_hint: int | None = None
    salary_currency_hint: str | None = None
    salary_interval_hint: str | None = None
    employment_mode_hint: str | None = None
    job_type_hint: str | None = None
    extra_hints: list[str] = field(default_factory=list)


@dataclass
class NormalizedJob:
    title: str
    company: str
    source: str
    location: str | None = None
    description: str | None = None
    company_logo: str | None = None
    type: str | None = None
    employment_mode: str | None = None
    experience_level: str | None = None
    min_salary: int | None = None
    max_salary: int | None = None
    salary_currency: str = "IDR"
    skills: list[str] = field(default_factory=list)
    contact_email: str | None = None
    contact_phone: str | None = None
    apply_url: str | None = None
    dedupe_key: str = ""
    url_hash: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

