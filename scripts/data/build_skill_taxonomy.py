"""Build SCPA skill taxonomy seed data from authorized public sources."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "skills" / "skills_seed.json"
DEFAULT_ALIAS_OUTPUT = REPO_ROOT / "data" / "skills" / "skill_aliases.json"

ESCO_API_URL = "https://ec.europa.eu/esco/api/search"
ONET_SOFTWARE_SKILLS_URL = "https://www.onetcenter.org/dl_files/database/db_30_3_text/Software%20Skills.txt"
ONET_ESSENTIAL_SKILLS_URL = "https://www.onetcenter.org/dl_files/database/db_30_3_text/Essential%20Skills.txt"

USER_AGENT = "SCPA academic local taxonomy builder (+https://esco.ec.europa.eu/; +https://www.onetcenter.org/)"


LOCAL_ALIASES: dict[str, list[str]] = {
    "Machine Learning": ["ml", "pembelajaran mesin"],
    "Artificial Intelligence": ["ai", "kecerdasan buatan"],
    "AI Agent": ["agen ai", "agentic ai"],
    "JavaScript": ["js"],
    "TypeScript": ["ts"],
    "React": ["reactjs", "react.js"],
    "Next.js": ["nextjs"],
    "Node.js": ["nodejs", "node"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "Kubernetes": ["k8s"],
    "PostgreSQL": ["postgres"],
    "Scikit-learn": ["sklearn", "scikit learn"],
    "Linux": ["gnu linux"],
    "Database Design": ["desain database"],
    "English": ["bahasa inggris", "inggris"],
    "Communication": ["komunikasi"],
    "Data Analysis": ["analisis data", "analisa data"],
    "Data Science": ["ilmu data"],
    "Data Engineering": ["rekayasa data"],
    "Credit Scoring": ["skor kredit", "pemodelan kredit"],
    "Credit Risk Modeling": ["risk model", "risk modeling", "model risiko"],
    "MLOps": ["machine learning operations"],
    "REST APIs": ["rest api", "restful api"],
    "Docker": ["containerization", "containers"],
    "Apache Airflow": ["airflow"],
    "Prefect": ["prefect orchestration"],
    "Git": ["version control"],
    "Model Versioning": ["model registry", "versioning models"],
    "Model Monitoring": ["model observability", "model performance monitoring"],
    "Terraform": ["infrastructure as code", "iac"],
    "Helm": ["helm charts"],
    "CI/CD": ["continuous integration", "continuous delivery"],
    "SQL": ["structured query language"],
    "Statistics": ["statistical analysis", "statistika"],
    "Certified Kubernetes Administrator": ["cka"],
    "AWS Certification": ["aws certified"],
}

LOCAL_CATEGORIES: dict[str, str] = {
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


def _request_text(url: str, timeout: int = 45) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official HTTPS URLs.
        return response.read().decode("utf-8-sig")


def _request_json(url: str, timeout: int = 45) -> dict[str, Any]:
    return json.loads(_request_text(url, timeout=timeout))


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _category_from_esco(result: dict[str, Any]) -> str:
    links = result.get("_links") or {}
    skill_types = links.get("hasSkillType") or []
    titles = {str(item.get("title") or "").lower() for item in skill_types if isinstance(item, dict)}
    if any("language" in title for title in titles):
        return "language"
    if any("knowledge" in title for title in titles):
        return "knowledge"
    if any("attitude" in title or "value" in title for title in titles):
        return "soft"
    return "technical"


def _upsert(rows: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    name = _norm(row.get("name"))
    if not name:
        return
    key = name.lower()
    existing = rows.setdefault(
        key,
        {
            "name": name,
            "category": row.get("category") or "technical",
            "aliases": set(),
            "source": row.get("source") or "local",
            "confidence": float(row.get("confidence") or 0.85),
        },
    )
    existing["aliases"].update(_norm(alias).lower() for alias in row.get("aliases", []) if _norm(alias))
    existing["aliases"].discard(key)
    existing["source"] = "+".join(
        sorted(set(str(existing.get("source") or "").split("+")) | {str(row.get("source") or "local")})
    ).strip("+")
    existing["confidence"] = max(float(existing.get("confidence") or 0.0), float(row.get("confidence") or 0.85))


def load_esco(limit: int | None = None, page_size: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total: int | None = None
    offset = 0
    while total is None or offset * page_size < total:
        query = urlencode(
            {
                "type": "skill",
                "language": "en",
                "limit": page_size,
                "offset": offset,
                "full": "true",
                "viewObsolete": "false",
            }
        )
        try:
            payload = _request_json(f"{ESCO_API_URL}?{query}")
        except (HTTPError, URLError, TimeoutError) as exc:
            if rows:
                print(f"warning: stopping ESCO fetch after {len(rows)} rows: {exc}", file=sys.stderr)
                break
            raise
        total = int(payload.get("total") or 0)
        results = ((payload.get("_embedded") or {}).get("results") or [])
        for result in results:
            if not isinstance(result, dict):
                continue
            label = result.get("preferredLabel") or {}
            aliases = result.get("alternativeLabel") or {}
            name = _norm(label.get("en") or result.get("title"))
            alias_values = aliases.get("en") if isinstance(aliases, dict) else []
            rows.append(
                {
                    "name": name,
                    "category": _category_from_esco(result),
                    "aliases": alias_values if isinstance(alias_values, list) else [],
                    "source": "ESCO v1.2.1 API",
                    "confidence": 0.92,
                }
            )
            if limit and len(rows) >= limit:
                return rows
        offset += 1
        if not results:
            break
    return rows


def load_onet() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    software_text = _request_text(ONET_SOFTWARE_SKILLS_URL)
    reader = csv.DictReader(software_text.splitlines(), delimiter="\t")
    for row in reader:
        name = _norm(row.get("Workplace Example"))
        element = _norm(row.get("Element Name")).lower()
        if not name:
            continue
        category = "tool" if "software" in element else "technical"
        rows.append(
            {
                "name": name,
                "category": category,
                "aliases": [element] if element else [],
                "source": "O*NET 30.3 Software Skills",
                "confidence": 0.88,
            }
        )

    essential_text = _request_text(ONET_ESSENTIAL_SKILLS_URL)
    reader = csv.DictReader(essential_text.splitlines(), delimiter="\t")
    seen_essential: set[str] = set()
    for row in reader:
        name = _norm(row.get("Element Name"))
        if not name or name.lower() in seen_essential:
            continue
        seen_essential.add(name.lower())
        rows.append(
            {
                "name": name,
                "category": "soft",
                "aliases": [],
                "source": "O*NET 30.3 Essential Skills",
                "confidence": 0.86,
            }
        )
    return rows


def build_taxonomy(esco_limit: int | None = None) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for row in load_esco(limit=esco_limit):
        _upsert(merged, row)
    for row in load_onet():
        _upsert(merged, row)
    for name, aliases in LOCAL_ALIASES.items():
        _upsert(
            merged,
            {
                "name": name,
                "category": LOCAL_CATEGORIES.get(name, "technical"),
                "aliases": aliases,
                "source": "local Indonesian aliases",
                "confidence": 1.0,
            },
        )

    skills = [
        {
            "name": row["name"],
            "category": row["category"],
            "aliases": sorted(row["aliases"]),
            "source": row["source"],
            "confidence": round(float(row["confidence"]), 3),
        }
        for row in merged.values()
    ]
    skills.sort(key=lambda item: item["name"].lower())
    return {
        "version": "esco-v1.2.1-onet-30.3-local-id-2026-06-01",
        "sources": [
            {
                "name": "ESCO v1.2.1",
                "url": "https://ec.europa.eu/esco/api/search?type=skill&language=en",
                "publisher": "European Commission DG Employment, Social Affairs and Inclusion",
            },
            {
                "name": "O*NET 30.3 Software Skills and Essential Skills",
                "url": "https://www.onetcenter.org/database.html",
                "publisher": "O*NET Resource Center",
            },
            {
                "name": "SCPA local Indonesian aliases",
                "url": "docs/data/SKILL_TAXONOMY_SOURCE.md",
                "publisher": "SCPA local project",
            },
        ],
        "count": len(skills),
        "skills": skills,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--aliases-output", type=Path, default=DEFAULT_ALIAS_OUTPUT)
    parser.add_argument(
        "--esco-limit",
        type=int,
        default=100,
        help="Bound ESCO API pagination. O*NET provides the remaining 5000+ entries.",
    )
    args = parser.parse_args(argv)

    taxonomy = build_taxonomy(esco_limit=args.esco_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.aliases_output.parent.mkdir(parents=True, exist_ok=True)
    args.aliases_output.write_text(json.dumps(LOCAL_ALIASES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {taxonomy['count']} skills to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
