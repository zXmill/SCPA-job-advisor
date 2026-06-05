"""Job contract type extraction."""

from __future__ import annotations


def detect_job_type(text: str | None, *, hint: str | None = None) -> str | None:
    haystack = f"{hint or ''} {text or ''}".lower().replace("-", "_")
    if any(token in haystack for token in ("internship", "intern", "magang")):
        return "internship"
    if any(token in haystack for token in ("contract", "kontrak", "freelance")):
        return "contract"
    if any(token in haystack for token in ("part_time", "part time", "paruh waktu")):
        return "part_time"
    if any(token in haystack for token in ("full_time", "full time", "permanent", "tetap")):
        return "full_time"
    return None

