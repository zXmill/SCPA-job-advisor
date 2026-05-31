"""Skill taxonomy and extraction."""

from __future__ import annotations

import re

from services.shared.skill_taxonomy import skill_alias_mapping


SKILL_ALIASES: dict[str, set[str]] = skill_alias_mapping()


def canonical_skill_count() -> int:
    return len(SKILL_ALIASES)


def _contains_alias(text: str, alias: str) -> bool:
    if " " in alias or "." in alias or "+" in alias or "#" in alias or "-" in alias:
        return alias in text
    return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) is not None


def extract_skills(
    text: str | None,
    *,
    max_results: int = 20,
    extra_hints: list[str] | None = None,
) -> list[str]:
    haystack = (text or "").lower()
    results: list[str] = []

    def add(skill: str) -> None:
        if skill not in results and len(results) < max_results:
            results.append(skill)

    for hint in extra_hints or []:
        hint_lower = str(hint).lower()
        for canonical, aliases in SKILL_ALIASES.items():
            if hint_lower == canonical.lower() or hint_lower in aliases:
                add(canonical)
                break

    for canonical, aliases in SKILL_ALIASES.items():
        if any(_contains_alias(haystack, alias) for alias in aliases):
            add(canonical)
        if len(results) >= max_results:
            break
    return results
