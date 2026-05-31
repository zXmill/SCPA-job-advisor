"""Skill taxonomy loading and lightweight matching helpers.

The runtime baseline comes from checked-in seed data under ``data/skills``.
The builder for that seed uses official ESCO and O*NET sources, then overlays
local Indonesian aliases for terms users actually type in SCPA.
"""

from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_SEED_PATH = REPO_ROOT / "data" / "skills" / "skills_seed.json"
DEFAULT_ALIAS_PATH = REPO_ROOT / "data" / "skills" / "skill_aliases.json"

LOCAL_SKILL_ALIASES: dict[str, set[str]] = {
    "Machine Learning": {"ml", "pembelajaran mesin"},
    "Artificial Intelligence": {"ai", "kecerdasan buatan"},
    "AI Agent": {"ai agent", "agentic ai", "agen ai"},
    "JavaScript": {"js"},
    "TypeScript": {"ts"},
    "React": {"reactjs", "react.js"},
    "Next.js": {"nextjs"},
    "Node.js": {"nodejs", "node"},
    "Tailwind CSS": {"tailwind", "tailwindcss"},
    "Kubernetes": {"k8s"},
    "PostgreSQL": {"postgres"},
    "Scikit-learn": {"sklearn", "scikit learn"},
    "Linux": {"gnu linux"},
    "Database Design": {"database design", "desain database"},
    "English": {"bahasa inggris", "inggris"},
    "Communication": {"komunikasi"},
    "Data Analysis": {"analisis data", "analisa data"},
    "Data Science": {"ilmu data"},
    "Data Engineering": {"rekayasa data"},
    "Credit Scoring": {"credit scoring", "skor kredit", "pemodelan kredit"},
    "Credit Risk Modeling": {"risk model", "risk modeling", "model risiko"},
    "MLOps": {"machine learning operations"},
    "REST APIs": {"rest api", "restful api"},
    "Docker": {"containerization", "containers"},
    "Apache Airflow": {"airflow"},
    "Prefect": {"prefect orchestration"},
    "Git": {"version control"},
    "Model Versioning": {"model registry", "versioning models"},
    "Model Monitoring": {"model observability", "model performance monitoring"},
    "Terraform": {"infrastructure as code", "iac"},
    "Helm": {"helm charts"},
    "CI/CD": {"continuous integration", "continuous delivery"},
    "SQL": {"structured query language"},
    "Statistics": {"statistical analysis", "statistika"},
    "Certified Kubernetes Administrator": {"cka"},
    "AWS Certification": {"aws certified"},
}

LOCAL_SKILL_CATEGORIES: dict[str, str] = {
    "AI Agent": "technical",
    "Apache Airflow": "tool",
    "Credit Risk Modeling": "domain",
    "Credit Scoring": "domain",
    "Data Engineering": "domain",
    "Data Science": "domain",
    "Docker": "tool",
    "English": "language",
    "Helm": "tool",
    "Kubernetes": "tool",
    "Model Monitoring": "knowledge",
    "Model Versioning": "knowledge",
    "Next.js": "framework",
    "Prefect": "tool",
    "React": "framework",
    "REST APIs": "technical",
    "Tailwind CSS": "framework",
    "Terraform": "tool",
    "Certified Kubernetes Administrator": "certification",
    "AWS Certification": "certification",
}


def normalize_skill_term(value: Any) -> str:
    """Normalize a term for search and deduplication."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _title_case_name(value: str) -> str:
    keep_upper = {
        "AI",
        "API",
        "APIs",
        "AWS",
        "BI",
        "CD",
        "CI",
        "CSS",
        "DQN",
        "ETL",
        "GCP",
        "HTML",
        "IT",
        "JSON",
        "KPI",
        "ML",
        "MLOps",
        "NCF",
        "NLP",
        "OOP",
        "REST",
        "SBERT",
        "SQL",
        "UI",
        "UX",
        "XML",
    }
    parts = []
    for part in str(value or "").strip().split():
        upper = part.upper().strip("()")
        if upper in keep_upper:
            parts.append(upper)
        elif part.lower() in {"and", "or", "of", "for", "to", "in"}:
            parts.append(part.lower())
        else:
            parts.append(part[:1].upper() + part[1:])
    return " ".join(parts)


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_skill_seed() -> tuple[dict[str, Any], ...]:
    """Load normalized skill rows from the configured seed file."""
    seed_path = Path(os.getenv("SCPA_SKILL_SEED_PATH", str(DEFAULT_SKILL_SEED_PATH)))
    raw_rows: list[dict[str, Any]] = []
    if seed_path.exists():
        payload = _load_json_file(seed_path)
        rows = payload.get("skills", payload) if isinstance(payload, dict) else payload
        if isinstance(rows, list):
            raw_rows.extend(row for row in rows if isinstance(row, dict))

    alias_path = Path(os.getenv("SCPA_SKILL_ALIAS_PATH", str(DEFAULT_ALIAS_PATH)))
    file_aliases: dict[str, set[str]] = {}
    if alias_path.exists():
        payload = _load_json_file(alias_path)
        if isinstance(payload, dict):
            for name, aliases in payload.items():
                values = aliases if isinstance(aliases, list) else [aliases]
                file_aliases[str(name)] = {str(alias) for alias in values if str(alias).strip()}

    merged: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        name = _title_case_name(str(row.get("name") or row.get("title") or "").strip())
        if not name:
            continue
        key = normalize_skill_term(name)
        aliases = {
            normalize_skill_term(alias)
            for alias in row.get("aliases", [])
            if normalize_skill_term(alias)
        }
        existing = merged.setdefault(
            key,
            {
                "name": name,
                "category": str(row.get("category") or "technical"),
                "aliases": set(),
                "source": str(row.get("source") or "local"),
                "confidence": float(row.get("confidence") or 0.85),
            },
        )
        existing["aliases"].update(aliases)
        existing["source"] = "+".join(
            sorted(set(str(existing.get("source") or "").split("+")) | {str(row.get("source") or "local")})
        ).strip("+")
        existing["confidence"] = max(float(existing.get("confidence") or 0.0), float(row.get("confidence") or 0.85))

    for name, aliases in {**LOCAL_SKILL_ALIASES, **file_aliases}.items():
        canonical = _title_case_name(name)
        key = normalize_skill_term(canonical)
        existing = merged.setdefault(
            key,
            {
                "name": canonical,
                "category": LOCAL_SKILL_CATEGORIES.get(canonical, "technical"),
                "aliases": set(),
                "source": "local_alias",
                "confidence": 1.0,
            },
        )
        existing["aliases"].update(normalize_skill_term(alias) for alias in aliases if normalize_skill_term(alias))
        existing["aliases"].discard(key)
        existing["source"] = "+".join(
            sorted(set(str(existing.get("source") or "").split("+")) | {"local_alias"})
        ).strip("+")
        existing["confidence"] = max(float(existing.get("confidence") or 0.0), 1.0)

    rows: list[dict[str, Any]] = []
    for row in merged.values():
        rows.append(
            {
                "name": row["name"],
                "category": str(row.get("category") or "technical")[:32],
                "aliases": sorted(alias for alias in row["aliases"] if alias and alias != normalize_skill_term(row["name"])),
                "source": str(row.get("source") or "local")[:64],
                "confidence": round(float(row.get("confidence") or 0.85), 3),
            }
        )
    return tuple(sorted(rows, key=lambda item: item["name"].lower()))


def skill_alias_mapping() -> dict[str, set[str]]:
    """Return canonical skill names mapped to normalized aliases."""
    mapping: dict[str, set[str]] = {}
    for row in load_skill_seed():
        aliases = {normalize_skill_term(row["name"]), *row.get("aliases", [])}
        mapping[str(row["name"])] = {alias for alias in aliases if alias}
    return mapping


def default_skill_taxonomy() -> tuple[dict[str, Any], ...]:
    return load_skill_seed()
