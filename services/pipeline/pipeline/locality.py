"""Indonesia-first locality checks for scraped jobs."""

from __future__ import annotations


LOCAL_SOURCES = {
    "jobstreet",
    "glints",
    "kalibrr",
    "karir",
    "topkarir",
    "kitalulus",
    "techinasia",
}

INDONESIA_TERMS = {
    "indonesia",
    "jakarta",
    "surabaya",
    "bandung",
    "depok",
    "tangerang",
    "bekasi",
    "yogyakarta",
    "semarang",
    "bali",
    "medan",
    "makassar",
    "unesa",
    "idr",
}


def has_indonesia_signal(
    *,
    source: str | None = None,
    location: str | None = None,
    description: str | None = None,
    salary_currency: str | None = None,
) -> bool:
    """Return true when a posting has enough evidence for Indonesia scope."""
    source_value = (source or "").strip().lower()
    if source_value in LOCAL_SOURCES:
        return True
    if (salary_currency or "").strip().upper() == "IDR":
        return True
    haystack = f"{location or ''} {description or ''}".lower()
    return any(term in haystack for term in INDONESIA_TERMS)

