"""Taxonomy extraction helpers for scraped job descriptions."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import text

from .skills import extract_skills

_KW_MODEL: Any | None = None
_KW_MODEL_UNAVAILABLE = False

_INDONESIAN_STOPWORDS = {
    "adalah",
    "akan",
    "atau",
    "dan",
    "dengan",
    "di",
    "dalam",
    "ini",
    "kami",
    "ke",
    "kerja",
    "memiliki",
    "menguasai",
    "untuk",
    "yang",
}


def _normalise_keyword(value: str) -> str:
    value = re.sub(r"[^\w.+# -]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def _keybert_model() -> Any | None:
    global _KW_MODEL, _KW_MODEL_UNAVAILABLE
    if _KW_MODEL is not None or _KW_MODEL_UNAVAILABLE:
        return _KW_MODEL
    try:
        from keybert import KeyBERT
    except ImportError:
        _KW_MODEL_UNAVAILABLE = True
        return None
    _KW_MODEL = KeyBERT("paraphrase-multilingual-MiniLM-L12-v2")
    return _KW_MODEL


def _fallback_keywords(text_value: str, top_n: int) -> list[tuple[str, float]]:
    words = [
        _normalise_keyword(word)
        for word in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{2,}", text_value)
    ]
    words = [w for w in words if w and w not in _INDONESIAN_STOPWORDS]
    counts = Counter(words)
    return [(word, min(0.6, 0.25 + count * 0.05)) for word, count in counts.most_common(top_n)]


def extract_taxonomy_terms(text_value: str | None, top_n: int = 10) -> list[dict[str, Any]]:
    """Return canonical skills plus optional keyword-enriched taxonomy terms."""

    source_text = text_value or ""
    terms: list[dict[str, Any]] = [
        {"skill": skill, "source": "canonical", "confidence": 1.0}
        for skill in extract_skills(source_text, max_results=top_n)
    ]
    seen = {_normalise_keyword(term["skill"]) for term in terms}

    model = _keybert_model()
    if model is None:
        keywords = _fallback_keywords(source_text, top_n)
    else:
        keywords = model.extract_keywords(
            source_text,
            keyphrase_ngram_range=(1, 2),
            stop_words=None,
            top_n=top_n,
        )

    for keyword, score in keywords:
        normalised = _normalise_keyword(str(keyword))
        if not normalised or normalised in seen or float(score) < 0.3:
            continue
        seen.add(normalised)
        terms.append(
            {
                "skill": normalised,
                "source": "keybert" if model is not None else "fallback_keyword",
                "confidence": round(float(score), 3),
            }
        )
    return terms


def upsert_taxonomy(db_session: Any, terms: list[dict[str, Any]]) -> int:
    """Upsert extracted terms into the controlled skills table."""

    counts = Counter(
        str(term.get("skill", "")).strip()
        for term in terms
        if str(term.get("skill", "")).strip()
    )
    inserted_or_updated = 0
    for skill, frequency in counts.items():
        db_session.execute(
            text(
                """
                INSERT INTO skills (name, category, frequency, updated_at)
                VALUES (:name, 'technical', :frequency, NOW())
                ON CONFLICT (name) DO UPDATE SET
                    frequency = skills.frequency + EXCLUDED.frequency,
                    updated_at = NOW()
                """
            ),
            {"name": skill, "frequency": frequency},
        )
        inserted_or_updated += 1
    return inserted_or_updated
