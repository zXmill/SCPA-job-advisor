"""Contact extraction helpers."""

from __future__ import annotations

import re


EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+62|62|0)\s?8[\d\s-]{7,15}")
TEMPLATE_DOMAINS = {"example.com", "example.org", "test.com", "localhost"}


def _normalise_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value)
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if not digits.startswith("62"):
        digits = "62" + digits
    return "+" + digits


def extract_contacts(text: str | None, *, max_results: int = 5) -> dict[str, list[str]]:
    if not text:
        return {"emails": [], "phones": []}
    emails: list[str] = []
    for email in EMAIL_RE.findall(text):
        domain = email.rsplit("@", 1)[-1].lower()
        if domain in TEMPLATE_DOMAINS:
            continue
        if email not in emails:
            emails.append(email)
        if len(emails) >= max_results:
            break

    phones: list[str] = []
    for raw in PHONE_RE.findall(text):
        phone = _normalise_phone(raw)
        if phone not in phones:
            phones.append(phone)
        if len(phones) >= max_results:
            break
    return {"emails": emails, "phones": phones}

