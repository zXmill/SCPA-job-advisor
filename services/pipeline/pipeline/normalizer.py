"""Normalize raw scraped postings into SCPA job records."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .extractors import (
    detect_job_type,
    extract_contacts,
    extract_employment_mode,
    extract_experience,
    extract_salary,
    extract_skills,
)
from .models import NormalizedJob, RawJobPosting, build_dedupe_key, build_url_hash


_SPACE_RE = re.compile(r"\s+")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return _SPACE_RE.sub(" ", value).strip()


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    return _clean(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def normalize(raw: RawJobPosting) -> NormalizedJob:
    description = _clean(raw.description) or _strip_html(raw.description_html) or ""
    salary = extract_salary(
        raw.salary_text or description,
        hint_min=raw.min_salary_hint,
        hint_max=raw.max_salary_hint,
        hint_currency=raw.salary_currency_hint,
        hint_interval=raw.salary_interval_hint,
    )
    contacts = extract_contacts(description)
    skills = extract_skills(
        f"{raw.title} {description}",
        extra_hints=raw.extra_hints,
    )
    return NormalizedJob(
        title=_clean(raw.title) or "",
        company=_clean(raw.company) or "",
        source=(raw.source or "").lower(),
        location=_clean(raw.location),
        description=description,
        company_logo=_clean(raw.company_logo),
        type=detect_job_type(description, hint=raw.job_type_hint),
        employment_mode=extract_employment_mode(
            description,
            location_hint=raw.employment_mode_hint or raw.location,
        ),
        experience_level=extract_experience(description, title_hint=raw.title),
        min_salary=salary.min_idr,
        max_salary=salary.max_idr,
        salary_currency=salary.raw_currency or "IDR",
        skills=skills,
        contact_email=contacts["emails"][0] if contacts["emails"] else None,
        contact_phone=contacts["phones"][0] if contacts["phones"] else None,
        apply_url=raw.apply_url,
        dedupe_key=build_dedupe_key(raw.title, raw.company, raw.location),
        url_hash=build_url_hash(raw.apply_url),
        raw={"salary_confidence": salary.confidence},
    )

