"""SCPA scraper service.

Provides lightweight scraping endpoints that extract job-like cards from static
HTML and public job-board JSON feeds. Browser-based scraping still belongs in
offline/debug jobs; this API path keeps request latency bounded while returning
real, schema-normalized jobs when a public feed is reachable.
"""

from __future__ import annotations

import hashlib
import asyncio
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass
from collections.abc import Iterable
from urllib.parse import quote_plus, urljoin, urlparse
from typing import Any, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI(
    title="SCPA Scraper Service",
    description="Latency-aware HTML job extraction and cleaning service",
    version="1.0.0",
)

DEFAULT_TIMEOUT_SECONDS = 8.0
USER_AGENT = "SCPA-Scraper/1.0 (+local academic project)"
_SPACE_RE = re.compile(r"\s+")
_DEFAULT_MAX_DESCRIPTION_CHARS = 1400
_MAX_SAFE_REDIRECTS = 5
SCRAPER_ALLOWED_HOST_SUFFIXES = {
    "linkedin.com",
    "indeed.com",
    "kalibrr.com",
    "karir.com",
    "jobstreet.com",
    "jobstreet.co.id",
    "glints.com",
    "techinasia.com",
    "remotive.com",
    "topkarir.com",
    "kitalulus.com",
}
LOCAL_SOURCE_HOSTS = {
    "id.linkedin.com",
    "www.linkedin.com",
    "id.indeed.com",
    "indeed.com",
    "www.kalibrr.com",
    "kalibrr.com",
    "karir.com",
    "www.karir.com",
    "www.jobstreet.co.id",
    "id.jobstreet.com",
    "glints.com",
    "www.techinasia.com",
}
INDONESIA_TERMS = {
    "indonesia",
    "jakarta",
    "surabaya",
    "bandung",
    "depok",
    "tangerang",
    "bekasi",
    "bogor",
    "yogyakarta",
    "semarang",
    "bali",
    "medan",
    "makassar",
    "batam",
    "subang",
    "jawa",
    "kalimantan",
    "sumatra",
    "sulawesi",
    "idr",
    "rp ",
}


def _is_allowed_scraper_host(hostname: str) -> bool:
    host = hostname.rstrip(".").lower()
    return any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in SCRAPER_ALLOWED_HOST_SUFFIXES
    )


def _is_unsafe_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return not ip.is_global


def _resolve_host_addresses(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="scraper URL host could not be resolved") from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise HTTPException(status_code=400, detail="scraper URL host could not be resolved")
    return addresses


def _validate_scrape_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="scraper URL scheme is not allowed")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="scraper URL host is required")

    host = parsed.hostname.rstrip(".").lower()
    try:
        if _is_unsafe_address(host):
            raise HTTPException(
                status_code=400,
                detail="scraper URL resolves to private or non-public address",
            )
        raise HTTPException(status_code=400, detail="scraper URL host is not allowed")
    except ValueError:
        pass

    if not _is_allowed_scraper_host(host):
        raise HTTPException(status_code=400, detail="scraper URL host is not allowed")

    for address in _resolve_host_addresses(host):
        if _is_unsafe_address(address):
            raise HTTPException(
                status_code=400,
                detail="scraper URL resolves to private or non-public address",
            )
    return url


async def _fetch_safe_url(
    client: httpx.AsyncClient,
    url: str,
    timeout: float | None = None,
) -> httpx.Response:
    current_url = _validate_scrape_url(url)
    for _ in range(_MAX_SAFE_REDIRECTS + 1):
        response = await client.get(current_url, timeout=timeout, follow_redirects=False)
        if not response.is_redirect:
            return response
        location = response.headers.get("location")
        if not location:
            raise HTTPException(status_code=400, detail="scraper URL redirect is missing a location")
        current_url = _validate_scrape_url(urljoin(str(response.url), location))
    raise HTTPException(status_code=400, detail="scraper URL redirect limit exceeded")


# Tech queries are kept so engineering candidates still flow through the
# pipeline; the non-tech queries below are additive so the candidate pool
# matches profiles outside software engineering (HR, finance, design, etc.).
SOURCE_QUERIES = [
    # Tech (existing — do not remove)
    "software engineer",
    "frontend developer",
    "backend developer",
    "python developer",
    "react developer",
    "web developer",
    "data engineer",
    "machine learning",
    "devops engineer",
    # Non-tech additions — required by recommendation fairness across majors.
    "human resources",
    "hr generalist",
    "talent acquisition",
    "finance",
    "accounting",
    "financial analyst",
    "marketing",
    "digital marketing",
    "content marketing",
    "sales",
    "account executive",
    "business development",
    "graphic design",
    "ui ux designer",
    "product designer",
    "operations",
    "supply chain",
    "logistics",
    "customer service",
    "customer success",
    "guru",
    "education",
    "teacher",
    "legal counsel",
    "paralegal",
    "perawat",
    "healthcare",
    "nurse",
]


SOURCE_URL_TEMPLATES: dict[str, list[str]] = {
    "kalibrr": [
        "https://www.kalibrr.com/home/te/indonesia",
        *[
            f"https://www.kalibrr.com/home/te/indonesia?keyword={quote_plus(query)}"
            for query in SOURCE_QUERIES
        ],
    ],
    "linkedin": [
        "https://www.linkedin.com/jobs/search?keywords={query}&location=Indonesia",
    ],
    "indeed": [
        "https://id.indeed.com/jobs?q={query}&l=Indonesia",
    ],
    "jobstreet": [
        "https://id.jobstreet.com/id/jobs?keywords={query}",
    ],
    "glints": [
        "https://glints.com/id/opportunities/jobs/explore?keyword={query}&country=ID",
    ],
    "karir": [
        "https://www.karir.com/search?q={query}",
    ],
    "techinasia": [
        "https://www.techinasia.com/jobs/search?query={query}&country_name%5B%5D=Indonesia",
    ],
}

SOURCE_ENV_FLAGS = {
    "linkedin": "PIPELINE_ENABLE_LINKEDIN",
    "indeed": "PIPELINE_ENABLE_INDEED",
    "jobstreet": "PIPELINE_ENABLE_JOBSTREET",
    "glints": "PIPELINE_ENABLE_GLINTS",
    "kalibrr": "PIPELINE_ENABLE_KALIBRR",
    "karir": "PIPELINE_ENABLE_KARIR",
    "techinasia": "PIPELINE_ENABLE_TECHINASIA",
}

SKILL_ALIASES: dict[str, set[str]] = {
    "Software Engineering": {"software engineer", "software engineering", "developer", "programmer"},
    "Python": {"python", "fastapi", "django", "pandas", "numpy"},
    "React": {"react", "reactjs", "react.js", "next.js", "nextjs"},
    "Web": {"web", "frontend", "front-end", "html", "css", "javascript", "typescript"},
    "SQL": {"sql", "postgresql", "postgres", "mysql", "database"},
    "Machine Learning": {"machine learning", "ml", "ai", "pytorch", "tensorflow", "scikit"},
    "Docker": {"docker", "container"},
    "Kubernetes": {"kubernetes", "k8s"},
    "Node.js": {"node.js", "nodejs", "node"},
    "JavaScript": {"javascript", "js"},
    "TypeScript": {"typescript", "ts"},
    "Data": {"data engineer", "data scientist", "analytics", "analyst", "etl"},
    # Non-tech tag mapping — keeps the inferred-skill fallback meaningful for
    # design/HR/finance/etc. roles even when the source page omits explicit
    # skill chips.
    "HR": {"human resources", "hr ", "talent acquisition", "rekrutmen", "recruiter", "people operations"},
    "Finance": {"finance", "akuntansi", "accounting", "auditor", "tax ", "treasury", "ppic"},
    "Marketing": {"marketing", "digital marketing", "content marketing", "seo", "sem", "branding", "copywriter"},
    "Sales": {"sales", "account executive", "business development", "bdr", "sdr", "inside sales"},
    "Design": {"design", "designer", "graphic design", "ui/ux", "ui ux", "figma", "canva", "adobe", "illustrator", "photoshop"},
    "Operations": {"operations", "operasional", "supply chain", "logistics", "warehouse", "procurement"},
    "Customer Service": {"customer service", "customer success", "cs ", "support specialist", "call center"},
    "Education": {"teacher", "guru", "education", "tutor", "lecturer", "dosen"},
    "Legal": {"legal", "lawyer", "paralegal", "compliance", "regulatory"},
    "Healthcare": {"healthcare", "nurse", "perawat", "dokter", "apoteker", "medical", "klinis", "clinical"},
}


@dataclass(frozen=True)
class SeedUrl:
    source: str
    url: str


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _source_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "linkedin" in host:
        return "linkedin"
    if "indeed" in host:
        return "indeed"
    if "jobstreet" in host:
        return "jobstreet"
    if "glints" in host:
        return "glints"
    if "kalibrr" in host:
        return "kalibrr"
    if "karir" in host:
        return "karir"
    if "techinasia" in host:
        return "techinasia"
    return "scraper"


def _canonical_source(source: str | None, source_url: str | None = None) -> str:
    cleaned = (source or "").strip().lower().replace("-", "").replace(" ", "")
    aliases = {"native": "", "seek": "jobstreet"}
    cleaned = aliases.get(cleaned, cleaned)
    allowed = set(SOURCE_ENV_FLAGS) | {"topkarir", "kitalulus", "remotive", "scraper"}
    if cleaned in allowed:
        return cleaned
    return _source_from_url(source_url or "")


def _enabled_sources() -> list[str]:
    enabled: list[str] = []
    for source, env_name in SOURCE_ENV_FLAGS.items():
        if _env_bool(env_name, True):
            enabled.append(source)
    return enabled


def _configured_seed_urls() -> list[SeedUrl]:
    raw = os.getenv("SCRAPER_SEED_URLS")
    if raw is not None and raw.strip():
        return [
            SeedUrl(source=_source_from_url(url.strip()), url=url.strip())
            for url in raw.split(",")
            if url.strip()
        ]
    if os.getenv("SCRAPER_SAMPLE_ONLY", "").strip().lower() in {"1", "true", "yes"}:
        return []
    seeds: list[SeedUrl] = []
    for source in _enabled_sources():
        templates = SOURCE_URL_TEMPLATES.get(source, [])
        for template in templates:
            if "{query}" in template:
                for query in SOURCE_QUERIES:
                    seeds.append(
                        SeedUrl(
                            source=source,
                            url=template.format(query=quote_plus(query)),
                        )
                    )
            else:
                seeds.append(SeedUrl(source=source, url=template))
    return seeds


class ScrapeUrlRequest(BaseModel):
    url: HttpUrl
    limit: int = Field(default=25, ge=1, le=100)


class ScrapeHtmlRequest(BaseModel):
    html: str = Field(min_length=1)
    source_url: Optional[str] = None
    limit: int = Field(default=25, ge=1, le=100)


class JobItem(BaseModel):
    job_id: str
    title: str
    description: str = ""
    company: str = ""
    company_logo: Optional[str] = None
    location: str = ""
    tags: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    source: Optional[str] = None
    salary_text: Optional[str] = None
    content_hash: str


class ScrapeResponse(BaseModel):
    count: int
    jobs: List[JobItem]
    deduplicated: int
    source_stats: list[dict[str, Any]] = Field(default_factory=list)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return _SPACE_RE.sub(" ", value).strip()


def _clean_html_text(value: Any, max_chars: int = _DEFAULT_MAX_DESCRIPTION_CHARS) -> str:
    if value is None:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip()


def _first_value(raw: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            for nested_key in ("name", "title", "label", "value", "url"):
                nested_value = value.get(nested_key)
                text = clean_text(str(nested_value)) if nested_value is not None else ""
                if text:
                    return text
            continue
        text = clean_text(str(value))
        if text:
            return text
    return ""


def _normalise_tags(value: Any) -> list[str]:
    raw_tags: list[str] = []
    if isinstance(value, list):
        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                text = _first_value(item, ["name", "title", "label", "value"])
            else:
                text = clean_text(str(item))
            if text:
                raw_tags.append(text)
    elif isinstance(value, str):
        raw_tags.extend(clean_text(part) for part in re.split(r"[,;/|]", value) if clean_text(part))

    tags: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags[:12]


def _infer_skills(*parts: str | None) -> list[str]:
    haystack = " ".join(part or "" for part in parts).lower()
    skills: list[str] = []
    for skill, aliases in SKILL_ALIASES.items():
        if any(alias in haystack for alias in aliases):
            skills.append(skill)
    return skills[:12]


def _nested_value(raw: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = raw
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _location_value(raw: dict[str, Any]) -> str:
    direct = _first_value(
        raw,
        ["candidate_required_location", "location", "city", "region", "country"],
    )
    if direct:
        return direct

    for key in ("locations", "jobLocations"):
        value = raw.get(key)
        if isinstance(value, list):
            names = []
            for item in value:
                if isinstance(item, dict):
                    text = _first_value(item, ["name", "city", "address", "location"])
                else:
                    text = clean_text(str(item))
                if text:
                    names.append(text)
            if names:
                return ", ".join(names[:3])

    address_components = _nested_value(raw, ("googleLocation", "addressComponents"))
    if isinstance(address_components, dict):
        parts = [
            clean_text(str(address_components.get(key) or ""))
            for key in ("city", "region", "country")
        ]
        return ", ".join(part for part in parts if part)
    return ""


def _source_url_value(raw: dict[str, Any], source_url: str | None) -> str:
    direct = _first_value(raw, ["url", "source_url", "apply_url", "job_url", "link", "applyRedirectUrl"])
    if direct:
        return urljoin(source_url or "", direct)

    refs = raw.get("refs")
    if isinstance(refs, dict):
        landing_page = clean_text(str(refs.get("landing_page") or ""))
        if landing_page:
            return urljoin(source_url or "", landing_page)

    slug = clean_text(str(raw.get("slug") or ""))
    job_id = clean_text(str(raw.get("id") or ""))
    company_code = _nested_value(raw, ("company", "code")) or _nested_value(raw, ("companyInfo", "code"))
    company_code = clean_text(str(company_code or ""))
    if slug and job_id and company_code:
        return f"https://www.kalibrr.com/c/{company_code}/jobs/{job_id}/{slug}"

    return source_url or ""


def _company_logo_value(raw: dict[str, Any], source_url: str | None) -> str:
    direct = _first_value(
        raw,
        ["company_logo", "company_logo_url", "logo", "logo_url", "companyLogo", "image"],
    )
    if direct:
        return urljoin(source_url or "", direct)

    for path in (
        ("companyInfo", "logoSmall"),
        ("companyInfo", "logo_160x90"),
        ("companyInfo", "logo"),
        ("company", "logoSmall"),
        ("company", "logo"),
    ):
        value = _nested_value(raw, path)
        text = clean_text(str(value)) if value is not None else ""
        if text:
            return urljoin(source_url or "", text)
    return ""


def _is_indonesia_job(job: "JobItem") -> bool:
    if os.getenv("SCRAPER_INDONESIA_ONLY", "true").strip().lower() in {"0", "false", "no"}:
        return True
    host = urlparse(job.source_url or "").hostname or ""
    if host.lower() in LOCAL_SOURCE_HOSTS:
        return True
    haystack = " ".join(
        [
            job.title,
            job.company,
            job.location,
            job.description,
            " ".join(job.tags),
            job.source_url or "",
        ]
    ).lower()
    return any(term in haystack for term in INDONESIA_TERMS)


def _filter_indonesia_jobs(jobs: list["JobItem"]) -> list["JobItem"]:
    return [job for job in jobs if _is_indonesia_job(job)]


def _fallback_logo(company: str) -> str | None:
    if not company:
        return None
    return (
        "https://ui-avatars.com/api/?name="
        f"{quote_plus(company)}&background=0D8ABC&color=fff&bold=true"
    )


def _first_text(node, selectors: list[str]) -> str:
    for selector in selectors:
        found = node.select_one(selector)
        text = clean_text(found.get_text(" ", strip=True) if found else "")
        if text:
            return text
    return ""


def _tag_texts(node) -> list[str]:
    tags: list[str] = []
    for selector in [".tag", ".tags li", "[data-tag]", ".chip", ".badge"]:
        for found in node.select(selector):
            text = clean_text(found.get_text(" ", strip=True) or found.get("data-tag"))
            if text and text.lower() not in {tag.lower() for tag in tags}:
                tags.append(text)
    return tags[:12]


def _company_logo(node, company: str, source_url: str | None) -> str | None:
    selectors = [
        "[data-company-logo]",
        "img.company-logo",
        "img.logo",
        ".company img",
        "img[alt*='logo' i]",
    ]
    for selector in selectors:
        found = node.select_one(selector)
        if not found:
            continue
        value = found.get("data-company-logo") or found.get("src") or found.get("data-src")
        if value:
            return urljoin(source_url or "", clean_text(value))
    return _fallback_logo(company)


def _content_hash(title: str, company: str, location: str) -> str:
    raw = f"{title.lower()}|{company.lower()}|{location.lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _job_item(
    *,
    title: str,
    company: str,
    location: str,
    description: str,
    tags: list[str],
    company_logo: str | None,
    source_url: str | None,
    source: str | None = None,
    salary_text: str | None = None,
) -> JobItem:
    digest = _content_hash(title, company, location)
    inferred_skills = _infer_skills(title, description, " ".join(tags))
    skills = tags or inferred_skills
    return JobItem(
        job_id=digest,
        title=title,
        description=description,
        company=company,
        company_logo=company_logo or _fallback_logo(company),
        location=location,
        tags=tags,
        skills=skills,
        source_url=source_url,
        source=_canonical_source(source, source_url),
        salary_text=salary_text or None,
        content_hash=digest,
    )


def _candidate_nodes(soup: BeautifulSoup):
    selectors = [
        "[data-job]",
        ".job",
        ".job-card",
        ".job-listing",
        ".vacancy",
        "article",
        "li",
    ]
    seen: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            marker = id(node)
            if marker not in seen:
                seen.add(marker)
                yield node


def extract_jobs(html: str, source_url: str | None = None, limit: int = 25) -> ScrapeResponse:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[JobItem] = []
    seen_hashes: set[str] = set()
    skipped_duplicates = 0

    for node in _candidate_nodes(soup):
        title = _first_text(
            node,
            [
                "[data-title]",
                ".title",
                ".job-title",
                "h1",
                "h2",
                "h3",
                "a",
            ],
        )
        if not title:
            continue

        company = _first_text(node, ["[data-company]", ".company", ".employer"])
        location = _first_text(node, ["[data-location]", ".location", ".city"])
        company_logo = _company_logo(node, company, source_url)
        description = _first_text(
            node,
            ["[data-description]", ".description", ".summary", "p"],
        )
        tags = _tag_texts(node)
        digest = _content_hash(title, company, location)

        if digest in seen_hashes:
            skipped_duplicates += 1
            continue
        seen_hashes.add(digest)
        jobs.append(
            _job_item(
                title=title,
                company=company,
                location=location,
                description=description,
                tags=tags,
                company_logo=company_logo,
                source_url=source_url,
                source=_source_from_url(source_url or ""),
            )
        )
        if len(jobs) >= limit:
            break

    jobs = _filter_indonesia_jobs(jobs)
    return ScrapeResponse(count=len(jobs), jobs=jobs, deduplicated=skipped_duplicates)


def _records_from_json(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("jobs", "results", "data", "items", "vacancies"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _records_from_json(value)
            if nested:
                return nested
    if any(key in payload for key in ("title", "job_title", "position", "company", "company_name")):
        return [payload]
    for value in payload.values():
        if isinstance(value, (dict, list)):
            nested = _records_from_json(value)
            if nested:
                return nested
    return []


def _salary_text_value(raw: dict[str, Any]) -> str | None:
    """Extract a free-text salary string from common job-board JSON shapes."""
    direct = _first_value(
        raw,
        [
            "salary_display",
            "salaryDisplay",
            "salary_text",
            "salaryText",
            "salary_range",
            "salaryRange",
            "salary",
            "salary_label",
            "compensation",
            "estimated_salary",
        ],
    )
    if direct:
        return direct
    base_salary = raw.get("baseSalary") or raw.get("base_salary")
    if isinstance(base_salary, dict):
        currency = clean_text(str(base_salary.get("currency") or ""))
        value = base_salary.get("value")
        if isinstance(value, dict):
            min_v = value.get("minValue") or value.get("min")
            max_v = value.get("maxValue") or value.get("max")
            unit = clean_text(str(value.get("unitText") or value.get("unit") or "")).lower()
            if min_v and max_v:
                return f"{currency} {min_v} - {max_v}{(' / ' + unit) if unit else ''}".strip()
            single = min_v or max_v
            if single:
                return f"{currency} {single}{(' / ' + unit) if unit else ''}".strip()
        elif isinstance(value, (int, float, str)) and value:
            return f"{currency} {value}".strip()
    for nested in ("salaryEstimate", "salary_estimate", "compensation_range"):
        nested_value = raw.get(nested)
        if isinstance(nested_value, dict):
            text = nested_value.get("text") or nested_value.get("display") or nested_value.get("value")
            if text:
                return clean_text(str(text))
    return None


_SALARY_TEXT_PATTERNS = (
    re.compile(
        r"(?:Rp|IDR|USD|SGD|MYR)\s?\.?\s*[\d.,]+(?:\s?-\s?(?:Rp|IDR)?\s?\.?\s*[\d.,]+)?(?:\s?(?:/\s?(?:bulan|month|jam|hour))?)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:Rp|IDR)\s?[\d.,]+\s?(?:juta|jt|million)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,3}(?:[.,]\d{3})+\s?(?:Rupiah|Rp)\b", re.IGNORECASE),
)


def _extract_salary_from_text(text: str | None) -> str | None:
    if not text:
        return None
    sample = text[:5000]
    for pattern in _SALARY_TEXT_PATTERNS:
        match = pattern.search(sample)
        if match:
            value = clean_text(match.group(0))
            if value and len(value) <= 120:
                return value
    return None


def extract_jobs_from_json(payload: Any, source_url: str | None = None, limit: int = 25) -> ScrapeResponse:
    jobs: list[JobItem] = []
    seen_hashes: set[str] = set()
    skipped_duplicates = 0

    for raw in _records_from_json(payload):
        title = _first_value(raw, ["title", "job_title", "position", "role", "name"])
        if not title:
            continue
        company = _first_value(
            raw,
            ["company_name", "companyName", "company", "organization", "employer", "hiring_company"],
        )
        location = _location_value(raw)
        description = _clean_html_text(
            raw.get("description")
            or raw.get("contents")
            or raw.get("summary")
            or raw.get("snippet")
            or raw.get("content")
            or raw.get("requirements")
        )
        raw_source_url = _source_url_value(raw, source_url)
        tags = _normalise_tags(
            raw.get("tags")
            or raw.get("skills")
            or raw.get("categories")
            or raw.get("category")
            or raw.get("job_type")
        )
        if not tags:
            tags = _normalise_tags([raw.get("category"), raw.get("job_type"), _nested_value(raw, ("company", "industry"))])
        inferred_skills = _infer_skills(title, description, " ".join(tags))
        if inferred_skills:
            tags = tags or inferred_skills
        company_logo = _company_logo_value(raw, source_url)
        salary_text = _salary_text_value(raw) or _extract_salary_from_text(description)
        digest = _content_hash(title, company, location)
        if digest in seen_hashes:
            skipped_duplicates += 1
            continue
        seen_hashes.add(digest)
        jobs.append(
            _job_item(
                title=title,
                company=company,
                location=location,
                description=description,
                tags=tags,
                company_logo=company_logo,
                source_url=raw_source_url or source_url,
                source=_first_value(raw, ["source", "job_source"]) or _source_from_url(raw_source_url or source_url or ""),
                salary_text=salary_text,
            )
        )
        if len(jobs) >= limit:
            break

    jobs = _filter_indonesia_jobs(jobs)
    return ScrapeResponse(count=len(jobs), jobs=jobs, deduplicated=skipped_duplicates)


def _extract_linkedin_jobs(soup: BeautifulSoup, source_url: str, limit: int) -> ScrapeResponse:
    jobs: list[JobItem] = []
    seen_hashes: set[str] = set()
    skipped_duplicates = 0
    for card in soup.select(".base-search-card, .job-search-card"):
        title = clean_text(
            (card.select_one(".base-search-card__title") or card.select_one("h3") or card).get_text(" ", strip=True)
        )
        if not title or title.lower() in {"easy apply", "under 10 applicants", "actively hiring"}:
            continue
        company = _first_text(card, [".base-search-card__subtitle", "h4", ".hidden-nested-link"])
        location = _first_text(card, [".job-search-card__location", ".base-search-card__metadata span"])
        link_node = card.select_one("a.base-card__full-link[href], a[href*='/jobs/view/']")
        job_url = urljoin(source_url, clean_text(link_node.get("href")) if link_node else source_url)
        logo_node = card.select_one("img[data-delayed-url], img[src]")
        logo = ""
        if logo_node:
            logo = logo_node.get("data-delayed-url") or logo_node.get("src") or ""
        description = " ".join(part for part in [title, company, location] if part)
        digest = _content_hash(title, company, location)
        if digest in seen_hashes:
            skipped_duplicates += 1
            continue
        seen_hashes.add(digest)
        jobs.append(
            _job_item(
                title=title,
                company=company,
                location=location or "Indonesia",
                description=description,
                tags=_infer_skills(title, description),
                company_logo=urljoin(source_url, clean_text(logo)) if logo else None,
                source_url=job_url,
                source="linkedin",
            )
        )
        if len(jobs) >= limit:
            break
    jobs = _filter_indonesia_jobs(jobs)
    return ScrapeResponse(count=len(jobs), jobs=jobs, deduplicated=skipped_duplicates)


def _extract_jobstreet_jobs(soup: BeautifulSoup, source_url: str, limit: int) -> ScrapeResponse:
    jobs: list[JobItem] = []
    seen_hashes: set[str] = set()
    skipped_duplicates = 0
    for card in soup.select("[data-testid='job-card'], article[data-job-id], article[data-automation='normalJob']"):
        title_node = card.select_one("[data-automation='jobTitle'], [data-testid='job-card-title'], h3 a")
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else card.get("aria-label", ""))
        if not title:
            continue
        company = _first_text(card, ["[data-automation='jobCompany']", "[data-type='company']"])
        location = _first_text(card, ["[data-automation='jobLocation']", "[data-automation='jobCardLocation']", "[data-type='location']"])
        desc = _first_text(card, ["[data-automation='jobShortDescription']", "[data-testid='job-card-teaser']", "ul", "p"])
        link = title_node.get("href") if title_node else ""
        if not link:
            link_node = card.select_one("a[href*='/id/job/']")
            link = link_node.get("href") if link_node else ""
        logo_node = card.select_one("[data-automation='company-logo'] img[src], [data-testid='company-logo-container'] img[src], img[src]")
        logo = logo_node.get("src") if logo_node else ""
        digest = _content_hash(title, company, location)
        if digest in seen_hashes:
            skipped_duplicates += 1
            continue
        seen_hashes.add(digest)
        description = desc or " ".join(part for part in [title, company, location] if part)
        jobs.append(
            _job_item(
                title=title,
                company=company,
                location=location or "Indonesia",
                description=description,
                tags=_infer_skills(title, description),
                company_logo=urljoin(source_url, clean_text(logo)) if logo else None,
                source_url=urljoin(source_url, clean_text(link)) if link else source_url,
                source="jobstreet",
            )
        )
        if len(jobs) >= limit:
            break
    jobs = _filter_indonesia_jobs(jobs)
    return ScrapeResponse(count=len(jobs), jobs=jobs, deduplicated=skipped_duplicates)


def _extract_next_data_payload(html: str) -> Any | None:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(BeautifulSoup(match.group(1), "html.parser").get_text())
    except json.JSONDecodeError:
        return None


def _parse_fetched_content(text: str, content_type: str, source_url: str, limit: int) -> ScrapeResponse:
    soup = BeautifulSoup(text, "html.parser")
    source = _source_from_url(source_url)
    if source == "linkedin":
        parsed = _extract_linkedin_jobs(soup, source_url, limit)
        if parsed.jobs:
            return parsed
    if source == "jobstreet":
        parsed = _extract_jobstreet_jobs(soup, source_url, limit)
        if parsed.jobs:
            return parsed
    is_json = "json" in content_type.lower() or text.lstrip().startswith(("{", "["))
    if is_json:
        try:
            return extract_jobs_from_json(json.loads(text), source_url=source_url, limit=limit)
        except json.JSONDecodeError:
            pass
    next_data = _extract_next_data_payload(text)
    if next_data is not None:
        parsed = extract_jobs_from_json(next_data, source_url=source_url, limit=limit)
        if parsed.jobs:
            return parsed
    return extract_jobs(text, source_url=source_url, limit=limit)


# ── Detail-page enrichment ─────────────────────────────────────────────────
#
# Listing-page parsers can only see a few hundred characters per card, so the
# cached description regularly looks like a title echo (e.g. "Senior DevOps
# Engineer Liven Gambir, Jakarta, Indonesia"). The helpers below visit the
# real job URL and pull the full body description plus a salary string when
# the source page exposes one. The fetch is bounded by concurrency and a hard
# per-job timeout so /scrape/run latency stays sane.

_DETAIL_FETCH_TIMEOUT_SECONDS = float(os.getenv("SCRAPER_DETAIL_TIMEOUT_SECONDS", "5"))
_DETAIL_FETCH_CONCURRENCY = int(os.getenv("SCRAPER_DETAIL_CONCURRENCY", "4"))
_DETAIL_FETCH_MAX_PER_RUN = int(os.getenv("SCRAPER_DETAIL_MAX_PER_RUN", "30"))
_DETAIL_FULL_DESC_MIN_CHARS = 200


def _is_thin_description(job: JobItem) -> bool:
    """A description is "thin" when it looks like the listing-card echo.

    Returns True if we should fetch the detail page to replace the body.
    """
    desc = clean_text(job.description or "")
    if not desc:
        return True
    if len(desc) < _DETAIL_FULL_DESC_MIN_CHARS:
        return True
    title = clean_text(job.title or "")
    company = clean_text(job.company or "")
    location = clean_text(job.location or "")
    title_echo = " ".join(part for part in [title, company, location] if part)
    if title_echo and desc.startswith(title_echo[: len(desc)]):
        return True
    return False


def _extract_detail_description(soup: BeautifulSoup) -> str:
    """Pull the full job-description body using known per-source selectors."""
    selectors = [
        # LinkedIn (logged-out public job page)
        ".show-more-less-html__markup",
        ".description__text",
        # JobStreet
        "[data-automation='jobAdDetails']",
        # Glints
        ".aljg ul, [class*='descriptionDetail']",
        # Kalibrr
        "[data-test='job-description']",
        ".text-content--initial",
        # Karir / Jobstreet fallback
        "article[class*='description']",
        "section[class*='description']",
        "[class*='job-description']",
        "[class*='JobDescription']",
        "main",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            if text and len(text) >= _DETAIL_FULL_DESC_MIN_CHARS:
                return text
    # JSON-LD JobPosting fallback covers most boards that ship structured data.
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.get_text() or "{}")
        except json.JSONDecodeError:
            continue
        candidates: list[Any] = []
        if isinstance(payload, list):
            candidates.extend(payload)
        elif isinstance(payload, dict):
            candidates.append(payload)
            graph = payload.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
        for item in candidates:
            if not isinstance(item, dict):
                continue
            ld_type = item.get("@type") or ""
            if "JobPosting" in (ld_type if isinstance(ld_type, str) else " ".join(ld_type)):
                description = item.get("description") or ""
                cleaned = _clean_html_text(description, max_chars=8000)
                if cleaned and len(cleaned) >= _DETAIL_FULL_DESC_MIN_CHARS:
                    return cleaned
    # Meta description as a last resort — at least never the bare title echo.
    meta = soup.select_one("meta[name='description'], meta[property='og:description']")
    if meta:
        text = clean_text(meta.get("content"))
        if text:
            return text
    return ""


def _extract_detail_salary(soup: BeautifulSoup, fallback_text: str | None = None) -> str | None:
    selectors = [
        "[data-automation='jobSalary']",
        "[data-test='job-salary']",
        "[class*='salary']",
        "[class*='Salary']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = clean_text(node.get_text(" ", strip=True))
            extracted = _extract_salary_from_text(text) or text
            if extracted and len(extracted) <= 120:
                return extracted
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.get_text() or "{}")
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if isinstance(item, dict):
                salary = _salary_text_value(item)
                if salary:
                    return salary
    if fallback_text:
        return _extract_salary_from_text(fallback_text)
    return None


async def _enrich_job_detail(client: httpx.AsyncClient, job: JobItem) -> JobItem:
    """Best-effort: replace a thin description and pull salary from the detail page."""
    url = job.source_url
    if not url:
        return job
    try:
        safe_url = _validate_scrape_url(url)
    except HTTPException:
        return job
    try:
        response = await _fetch_safe_url(client, safe_url, timeout=_DETAIL_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError:
        return job
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        return job
    soup = BeautifulSoup(response.text, "html.parser")
    description = _extract_detail_description(soup) or job.description
    salary = job.salary_text or _extract_detail_salary(soup, fallback_text=description)
    if description == job.description and salary == job.salary_text:
        return job
    update = job.model_copy(
        update={
            "description": description or job.description,
            "salary_text": salary,
        }
    )
    return update


async def _enrich_jobs_with_detail(
    client: httpx.AsyncClient, jobs: list[JobItem]
) -> list[JobItem]:
    """Concurrently enrich up to N thin-description jobs with their detail body."""
    targets = [job for job in jobs if _is_thin_description(job) and job.source_url]
    if not targets:
        return jobs
    targets = targets[:_DETAIL_FETCH_MAX_PER_RUN]
    semaphore = asyncio.Semaphore(max(1, _DETAIL_FETCH_CONCURRENCY))

    async def _runner(job: JobItem) -> tuple[str, JobItem]:
        async with semaphore:
            return job.content_hash, await _enrich_job_detail(client, job)

    enriched_pairs = await asyncio.gather(
        *[_runner(job) for job in targets], return_exceptions=False
    )
    enriched = {content_hash: job for content_hash, job in enriched_pairs}
    return [enriched.get(job.content_hash, job) for job in jobs]


@app.get("/health")
async def health_check():
    seeds = _configured_seed_urls()
    return {
        "status": "healthy",
        "service": "scraper",
        "parser": "beautifulsoup+json",
        "seed_urls_configured": len(seeds),
        "enabled_sources": sorted({seed.source for seed in seeds}),
    }


@app.post("/scrape/html", response_model=ScrapeResponse)
async def scrape_html(request: ScrapeHtmlRequest):
    return extract_jobs(
        request.html,
        source_url=request.source_url,
        limit=request.limit,
    )


@app.post("/scrape/url", response_model=ScrapeResponse)
async def scrape_url(request: ScrapeUrlRequest):
    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await _fetch_safe_url(client, str(request.url))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "json" not in content_type.lower():
        text = response.text
        if not text.lstrip().startswith(("{", "[")):
            raise HTTPException(status_code=415, detail="URL did not return HTML or JSON")
    return _parse_fetched_content(response.text, content_type, str(request.url), request.limit)


@app.post("/scrape/run", response_model=ScrapeResponse)
async def scrape_run(limit: int = 100):
    """Run one configured scrape cycle.

    Set `SCRAPER_SEED_URLS` to a comma-separated list of HTML job-board/search
    URLs or public job API URLs. When live URLs are unavailable or return no
    jobs, the service returns local sample data so the rest of the ML pipeline
    remains testable.
    """
    seed_urls = _configured_seed_urls()
    if not seed_urls:
        return await sample()

    all_jobs: list[JobItem] = []
    deduplicated = 0
    source_stats: list[dict[str, Any]] = []
    target = max(1, min(int(limit or 100), int(os.getenv("JOBS_TARGET", "2000"))))
    max_urls = max(1, int(os.getenv("SCRAPER_MAX_URLS_PER_RUN", "80")))
    concurrency = max(1, int(os.getenv("SCRAPER_CONCURRENCY", "6")))
    selected_urls = seed_urls[:max_urls]
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_seed(client: httpx.AsyncClient, seed: SeedUrl) -> tuple[SeedUrl, ScrapeResponse | None, str | None]:
        async with semaphore:
            try:
                response = await _fetch_safe_url(client, seed.url)
                response.raise_for_status()
                parsed = _parse_fetched_content(
                    response.text,
                    response.headers.get("content-type", ""),
                    seed.url,
                    target,
                )
                return seed, parsed, None
            except httpx.HTTPError as exc:
                return seed, None, str(exc)

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        results = await asyncio.gather(*(fetch_seed(client, seed) for seed in selected_urls))
        for seed, parsed, error in results:
            if parsed:
                all_jobs.extend(parsed.jobs)
                deduplicated += parsed.deduplicated
                source_stats.append(
                    {
                        "source": seed.source,
                        "url": seed.url,
                        "count": parsed.count,
                        "deduplicated": parsed.deduplicated,
                        "status": "ok",
                    }
                )
            else:
                source_stats.append(
                    {
                        "source": seed.source,
                        "url": seed.url,
                        "count": 0,
                        "deduplicated": 0,
                        "status": "failed",
                        "error": error,
                    }
                )

        seen: set[str] = set()
        jobs_by_source: dict[str, list[JobItem]] = {}
        for job in all_jobs:
            if job.content_hash in seen:
                deduplicated += 1
                continue
            seen.add(job.content_hash)
            jobs_by_source.setdefault(job.source or "scraper", []).append(job)
        unique: list[JobItem] = []
        while len(unique) < target and any(jobs_by_source.values()):
            for source in sorted(jobs_by_source):
                bucket = jobs_by_source[source]
                if not bucket:
                    continue
                unique.append(bucket.pop(0))
                if len(unique) >= target:
                    break
        if not unique:
            return await sample()

        # Bounded detail-page enrichment: pulls full description + salary_text
        # for the top N jobs whose listing-card description is just the title
        # echo. Disabled with SCRAPER_DETAIL_MAX_PER_RUN=0 if needed.
        enriched_jobs = unique[:target]
        if _DETAIL_FETCH_MAX_PER_RUN > 0:
            enriched_jobs = await _enrich_jobs_with_detail(client, enriched_jobs)
    return ScrapeResponse(
        count=len(enriched_jobs),
        jobs=enriched_jobs,
        deduplicated=deduplicated,
        source_stats=source_stats,
    )


@app.get("/sample", response_model=ScrapeResponse)
async def sample():
    html = """
    <article class="job-card">
      <h2 class="job-title">Data Scientist Junior</h2>
      <div class="company">PT Tokopedia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Bergabung dengan tim data science kami untuk mengembangkan model prediktif menggunakan Python, TensorFlow, dan SQL. Menganalisis data pengguna untuk meningkatkan rekomendasi produk.</p>
      <span class="tag">Python</span><span class="tag">TensorFlow</span><span class="tag">SQL</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Product Manager</h2>
      <div class="company">Gojek</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Memimpin pengembangan produk digital untuk jutaan pengguna di Asia Tenggara. Membutuhkan kemampuan analitik data, Agile/Scrum, dan stakeholder management.</p>
      <span class="tag">Product Management</span><span class="tag">Agile</span><span class="tag">Scrum</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Frontend Engineer</h2>
      <div class="company">Bukalapak</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Membangun antarmuka pengguna yang responsif menggunakan React, TypeScript, dan Next.js. Pengalaman dengan design system dan testing framework diutamakan.</p>
      <span class="tag">React</span><span class="tag">TypeScript</span><span class="tag">Next.js</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Senior Data Analyst</h2>
      <div class="company">Gopay Indonesia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Menganalisis data transaksi fintech untuk mendukung keputusan strategis. Keahlian SQL, Tableau, Python, dan statistical modeling diperlukan.</p>
      <span class="tag">SQL</span><span class="tag">Tableau</span><span class="tag">Python</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Machine Learning Engineer</h2>
      <div class="company">Traveloka</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Membangun dan deploy model ML untuk personalisasi harga dan rekomendasi perjalanan. PyTorch, MLOps, dan cloud infrastructure (AWS/GCP).</p>
      <span class="tag">PyTorch</span><span class="tag">MLOps</span><span class="tag">Python</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Backend Engineer (Go)</h2>
      <div class="company">Shopee Indonesia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Mengembangkan microservices menggunakan Go, gRPC, dan Kubernetes. Membutuhkan pengalaman distributed systems dan high-throughput architectures.</p>
      <span class="tag">Go</span><span class="tag">gRPC</span><span class="tag">Kubernetes</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">DevOps Engineer</h2>
      <div class="company">OVO</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Mengelola infrastructure CI/CD, Docker, Kubernetes, dan monitoring. Pengalaman AWS, Terraform, dan observability stack (Prometheus, Grafana).</p>
      <span class="tag">Docker</span><span class="tag">Kubernetes</span><span class="tag">AWS</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">UI/UX Designer</h2>
      <div class="company">Blibli.com</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Merancang pengalaman pengguna e-commerce. Figma, user research, prototyping, design system. Portofolio desain interaksi diperlukan.</p>
      <span class="tag">Figma</span><span class="tag">UI/UX</span><span class="tag">Prototyping</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Cloud Solutions Architect</h2>
      <div class="company">Google Indonesia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Membantu enterprise Indonesia mengadopsi Google Cloud. Keahlian cloud architecture, networking, security, dan data analytics di GCP.</p>
      <span class="tag">Google Cloud</span><span class="tag">Cloud Architecture</span><span class="tag">Security</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Cybersecurity Analyst</h2>
      <div class="company">Bank Mandiri</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Monitoring keamanan sistem perbankan, incident response, dan vulnerability assessment. Sertifikasi CompTIA Security+ atau CEH diutamakan.</p>
      <span class="tag">Cybersecurity</span><span class="tag">Incident Response</span><span class="tag">Security</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Data Engineer</h2>
      <div class="company">Grab Indonesia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Membangun data pipeline dan data warehouse menggunakan Apache Spark, Airflow, dan BigQuery. ETL optimization dan data quality monitoring.</p>
      <span class="tag">Apache Spark</span><span class="tag">Airflow</span><span class="tag">BigQuery</span>
    </article>
    <article class="job-card">
      <h2 class="job-title">Mobile Developer (Flutter)</h2>
      <div class="company">Dana Indonesia</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Mengembangkan aplikasi mobile fintech dengan Flutter/Dart. Pengalaman REST API integration, state management, dan app performance optimization.</p>
      <span class="tag">Flutter</span><span class="tag">Dart</span><span class="tag">Mobile</span>
    </article>
    """
    return extract_jobs(html, source_url="sample://local", limit=20)
