"""Structured job-description parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
import re
from typing import Any

from bs4 import BeautifulSoup


SECTION_ALIASES: tuple[tuple[str, str], ...] = (
    ("who_we_are", "about us"),
    ("who_we_are", "about the company"),
    ("who_we_are", "about astro"),
    ("who_we_are", "who we are"),
    ("why_join_us", "why join us"),
    ("why_join_us", "why this role is different"),
    ("role_overview", "role overview"),
    ("role_overview", "about this position"),
    ("responsibilities", "job responsibilities"),
    ("responsibilities", "job description"),
    ("responsibilities", "responsibilities"),
    ("responsibilities", "what you'll be doing"),
    ("responsibilities", "what you’ll be doing"),
    ("responsibilities", "your missions are"),
    ("responsibilities", "technical & engineering focus"),
    ("responsibilities", "data & performance analysis"),
    ("responsibilities", "cross-functional collaboration"),
    ("requirements", "job requirements"),
    ("requirements", "requirements"),
    ("requirements", "qualifications"),
    ("requirements", "essential criteria"),
    ("requirements", "what we're looking for"),
    ("requirements", "what we’re looking for"),
    ("nice_to_have", "nice to have"),
    ("nice_to_have", "preferred qualifications"),
    ("nice_to_have", "our stack"),
    ("benefits", "benefits"),
    ("benefits", "what we offer"),
    ("benefits", "how to apply"),
)

METADATA_LABELS: dict[str, tuple[str, ...]] = {
    "seniority_level": ("seniority level", "tingkat senioritas"),
    "employment_type": ("employment type", "jenis pekerjaan"),
    "job_function": ("job function", "fungsi pekerjaan"),
    "industry": ("industry", "industri"),
    "education_level": ("education", "pendidikan"),
}

_SPACE_RE = re.compile(r"\s+")
_YEARS_RE = re.compile(r"(?P<min>\d+)(?:\s*[-–]\s*(?P<max>\d+))?\s*\+?\s*(?:years?|tahun)", re.I)


@dataclass(frozen=True)
class ParsedJobDescription:
    raw_description_html: str | None = None
    description_text: str = ""
    description_sections: dict[str, str] = field(default_factory=dict)
    responsibilities: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    seniority_level: str | None = None
    employment_type: str | None = None
    job_function: str | None = None
    industry: str | None = None
    education_level: str | None = None
    years_experience_min: int | None = None
    years_experience_max: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_description_html": self.raw_description_html,
            "description_text": self.description_text,
            "description_sections": self.description_sections,
            "responsibilities": self.responsibilities,
            "requirements": self.requirements,
            "nice_to_have": self.nice_to_have,
            "benefits": self.benefits,
            "seniority_level": self.seniority_level,
            "employment_type": self.employment_type,
            "job_function": self.job_function,
            "industry": self.industry,
            "education_level": self.education_level,
            "years_experience_min": self.years_experience_min,
            "years_experience_max": self.years_experience_max,
        }


def clean_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", unescape(str(value or ""))).strip()


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def _canonical_section(line: str) -> str | None:
    normal = clean_text(line).lower().strip(":")
    for canonical, alias in SECTION_ALIASES:
        if normal == alias or normal.startswith(f"{alias}:"):
            return canonical
    return None


def _split_section_lines(text: str) -> list[str]:
    prepared = text
    for _canonical, alias in SECTION_ALIASES:
        prepared = re.sub(
            rf"(?i)(?<!\w)({re.escape(alias)})\s*:?",
            r"\n\1\n",
            prepared,
        )
    for labels in METADATA_LABELS.values():
        for label in labels:
            prepared = re.sub(
                rf"(?i)(?<!\w)({re.escape(label)})\s*:?",
                r"\n\1: ",
                prepared,
            )
    return [clean_text(line) for line in prepared.splitlines() if clean_text(line)]


def _parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "description"
    for line in _split_section_lines(text):
        section = _canonical_section(line)
        if section:
            current = section
            remainder = re.sub(r"(?i)^" + re.escape(line.strip(":")) + r"\s*:?", "", line).strip()
            if remainder:
                sections.setdefault(current, []).append(remainder)
            continue
        sections.setdefault(current, []).append(line)
    return {key: clean_text(" ".join(values)) for key, values in sections.items() if clean_text(" ".join(values))}


def _list_from_section(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"(?:\s*[•*]\s+)|(?:\s+-\s+)|(?:\.\s+(?=[A-Z]))", value)
    cleaned = [clean_text(part).strip(" .;") for part in parts if len(clean_text(part)) >= 8]
    return cleaned[:24]


def _extract_metadata(text: str) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {key: None for key in METADATA_LABELS}
    lines = _split_section_lines(text)
    for line in lines:
        lower = line.lower()
        for key, labels in METADATA_LABELS.items():
            for label in labels:
                if lower.startswith(label):
                    value = clean_text(re.sub(rf"(?i)^{re.escape(label)}\s*:?", "", line))
                    if value:
                        metadata[key] = value[:255]
    return metadata


def _extract_years(text: str) -> tuple[int | None, int | None]:
    matches = list(_YEARS_RE.finditer(text))
    if not matches:
        return None, None
    mins = [int(match.group("min")) for match in matches]
    maxes = [int(match.group("max") or match.group("min")) for match in matches]
    return min(mins), max(maxes)


def parse_job_description(
    description_text: str | None = None,
    raw_description_html: str | None = None,
) -> ParsedJobDescription:
    """Parse a job detail page body into stable structured fields."""
    text = clean_text(description_text) or html_to_text(raw_description_html)
    raw_html = raw_description_html if raw_description_html and "<" in raw_description_html else None
    sections = _parse_sections(text)
    metadata = _extract_metadata(text)
    years_min, years_max = _extract_years(text)
    return ParsedJobDescription(
        raw_description_html=raw_html,
        description_text=text,
        description_sections=sections,
        responsibilities=_list_from_section(sections.get("responsibilities")),
        requirements=_list_from_section(sections.get("requirements")),
        nice_to_have=_list_from_section(sections.get("nice_to_have")),
        benefits=_list_from_section(sections.get("benefits")),
        seniority_level=metadata["seniority_level"],
        employment_type=metadata["employment_type"],
        job_function=metadata["job_function"],
        industry=metadata["industry"],
        education_level=metadata["education_level"],
        years_experience_min=years_min,
        years_experience_max=years_max,
    )
