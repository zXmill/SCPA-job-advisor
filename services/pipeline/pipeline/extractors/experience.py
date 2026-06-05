"""Experience level extraction."""

from __future__ import annotations

import re


def extract_experience(text: str | None, *, title_hint: str | None = None) -> str | None:
    haystack = f"{title_hint or ''} {text or ''}".lower()
    if any(token in haystack for token in ("intern", "internship", "magang", "fresh graduate", "junior")):
        return "entry"
    if any(token in haystack for token in ("senior", "lead", "principal", "manager")):
        return "senior"

    match = re.search(r"(\d+)\s*(?:[-–]\s*(\d+))?\s*(?:years?|tahun)", haystack)
    if match:
        years = int(match.group(2) or match.group(1))
        if years >= 6:
            return "senior"
        if years >= 2:
            return "mid"
        return "entry"
    return None

