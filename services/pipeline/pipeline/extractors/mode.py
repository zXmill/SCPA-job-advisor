"""Employment mode extraction."""

from __future__ import annotations


def extract_employment_mode(text: str | None, *, location_hint: str | None = None) -> str | None:
    haystack = f"{text or ''} {location_hint or ''}".lower()
    remote = any(token in haystack for token in ("remote", "wfh", "work from home"))
    onsite = any(token in haystack for token in ("wfo", "onsite", "on-site", "in-office", "office"))
    if "hybrid" in haystack or (remote and onsite):
        return "hybrid"
    if remote:
        return "remote"
    if onsite:
        return "onsite"
    return None

