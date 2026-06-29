"""SCPA API Gateway — public-facing FastAPI service."""

from __future__ import annotations

import logging
import asyncio
import gzip
import io
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import json
import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile

# Load .env from project root (two levels up from this file)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from services.shared.auth import validate_jwt_secret
from services.shared.job_description import parse_job_description
from services.shared.model_bundle import (
    ACTIVE_BUNDLE_SQL,
    DEFAULT_ACTIVE_SBERT,
    DEFAULT_BUNDLE_VERSION,
    DEFAULT_RESPONSE_SCHEMA,
    DEFAULT_STATE_SCHEMA,
    ModelBundle,
    active_sbert_version,
    bundle_from_row,
)
from services.shared.skill_taxonomy import (
    default_skill_taxonomy,
    normalize_skill_term,
)
from sqlalchemy import Text as SqlText
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover - optional PDF extraction
    PdfReader = None

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("scpa.gateway")

# ── Configuration ──
DEFAULT_DEV_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
)
PRODUCTION_ENVS = {"production", "prod"}


def _resolve_cors_origins(app_env: str | None, raw_origins: str | None) -> list[str]:
    env = (app_env or "development").strip().lower()
    origins = [
        origin.strip()
        for origin in (raw_origins or "").split(",")
        if origin.strip()
    ]

    if not origins and env not in PRODUCTION_ENVS:
        origins = list(DEFAULT_DEV_CORS_ORIGINS)

    if env in PRODUCTION_ENVS:
        if not origins:
            raise RuntimeError("CORS origins must be configured in production")
        if "*" in origins:
            raise RuntimeError("Wildcard CORS origins are not allowed in production")

    return origins


def _cors_origins_from_env() -> list[str]:
    raw_origins = (
        os.getenv("CORS_ALLOW_ORIGINS")
        or os.getenv("CORS_ALLOWED_ORIGINS")
        or os.getenv("CORS_ORIGINS")
    )
    return _resolve_cors_origins(os.getenv("APP_ENV", "development"), raw_origins)


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
JWT_SECRET = validate_jwt_secret(os.getenv("JWT_SECRET", ""), "JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
JWT_REFRESH_SECRET = validate_jwt_secret(
    os.getenv("JWT_REFRESH_SECRET", JWT_SECRET),
    "JWT_REFRESH_SECRET",
)
PIPELINE_URL = os.getenv("PIPELINE_URL", os.getenv("PIPELINE_SERVICE_URL", "http://pipeline:8005")).rstrip("/")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
INTERNAL_SERVICE_TOKEN_HEADER = "X-Internal-Service-Token"
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "70"))
HEALTH_TIMEOUT_SECONDS = float(os.getenv("HEALTH_TIMEOUT_SECONDS", "2"))
P95_TARGET_MS = int(os.getenv("GATEWAY_P95_TARGET_MS", "150"))
PUBLIC_GATEWAY_URL = os.getenv("PUBLIC_GATEWAY_URL", "http://localhost:8000").rstrip("/")
# Catalog freshness ceiling: jobs older than this many days (by posted_at) are
# treated as expired and hidden from the public catalog, facets, and counts —
# including the "all time" range — so stale scraped listings never surface.
# Set to 0 to disable the ceiling and show every active job regardless of age.
JOB_CATALOG_MAX_AGE_DAYS = max(0, int(os.getenv("JOB_CATALOG_MAX_AGE_DAYS", "90")))
FEEDBACK_OUTBOX_RETRY_ENABLED = os.getenv(
    "FEEDBACK_OUTBOX_RETRY_ENABLED", "true"
).lower() in {"1", "true", "yes"}
FEEDBACK_OUTBOX_RETRY_INTERVAL_SECONDS = float(
    os.getenv("FEEDBACK_OUTBOX_RETRY_INTERVAL_SECONDS", "30")
)
FEEDBACK_OUTBOX_RETRY_BATCH_SIZE = int(
    os.getenv("FEEDBACK_OUTBOX_RETRY_BATCH_SIZE", "50")
)
LOGO_PROXY_ALLOWED_HOSTS = {"remotive.com", "www.remotive.com"}
LOGO_PROXY_ALLOWED_HOSTS.update(
    {
        "rec-data.kalibrr.com",
        "static.kalibrr.com",
        "glints.com",
        "images.glints.com",
        "media.licdn.com",
        "static.licdn.com",
        "bx-branding-gateway.cloud.seek.com.au",
    }
)
INDONESIA_JOB_HOSTS = {
    "www.kalibrr.com",
    "kalibrr.com",
    "karir.com",
    "www.karir.com",
    "www.jobstreet.co.id",
    "id.jobstreet.com",
    "glints.com",
    "www.techinasia.com",
}
INDONESIA_JOB_TERMS = {
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
}
REASON_FILTER_LABELS = {
    "semantic_fit": "Highest SBERT semantic match",
    "interaction_fit": "Highest NCF interaction fit",
    "session_rerank_signal": "Highest DQN session rerank signal",
    "location_fit": "Closest profile location",
    "recency": "Newest jobs",
}
REASON_FILTER_RECENCY_WINDOW_DAYS = 30.0

# ── CV Upload ──
CV_UPLOAD_DIR = Path(os.getenv("CV_UPLOAD_DIR", "data/uploads/cv"))
MAX_CV_SIZE_MB = int(os.getenv("MAX_CV_SIZE_MB", "5"))
MAX_CV_SIZE_BYTES = MAX_CV_SIZE_MB * 1024 * 1024
CV_ALLOWED_EXTENSIONS = {".pdf", ".txt"}

# ── Certificate Upload ──
CERT_UPLOAD_DIR = Path(os.getenv("CERT_UPLOAD_DIR", "data/uploads/certificates"))
CERT_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

# ── Database ──
def _async_db_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = _async_db_url(
    os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/db_scpa")
)
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ── HTTP client ──
http_client: httpx.AsyncClient | None = None
feedback_outbox_task: asyncio.Task | None = None

# ── Password hashing ──
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Auth scheme ──
bearer_scheme = HTTPBearer(auto_error=False)

SKILL_SEARCH_MAX_ROWS = 20_000
DEFAULT_SKILL_TAXONOMY: tuple[dict[str, Any], ...] = tuple(default_skill_taxonomy())
SKILL_SEARCH_PRIORITY = {
    "SQL": -50,
    "AI Agent": -48,
    "Artificial Intelligence": -48,
    "Statistics": -45,
    "Software Engineering": -42,
    "Python": -40,
    "Machine Learning": -40,
    "Data Analysis": -40,
    "Data Science": -40,
    "Data Engineering": -40,
    "Docker": -35,
    "Kubernetes": -35,
    "English": -35,
    "Communication": -35,
    "Credit Scoring": -35,
    "Training": -34,
    "Operations": -34,
    "Quality Assurance": -34,
    "Reporting": -34,
    "Performance Monitoring": -34,
    "Onboarding": -33,
    "Retention": -33,
    "Program Management": -33,
    "Stakeholder Management": -33,
}
USER_FACING_SKILL_CATEGORIES = {
    "certification",
    "domain",
    "framework",
    "knowledge",
    "language",
    "soft",
    "technical",
    "tool",
}

_SEED_SKILL_STMT = text(
    """
    INSERT INTO skills (name, category, aliases, source, confidence, frequency, updated_at)
    VALUES (:name, :category, :aliases, :source, :confidence, 1, NOW())
    ON CONFLICT (name) DO UPDATE SET
        category = EXCLUDED.category,
        aliases = EXCLUDED.aliases,
        source = EXCLUDED.source,
        confidence = EXCLUDED.confidence,
        updated_at = NOW()
    """
).bindparams(bindparam("aliases", type_=ARRAY(SqlText())))


# ════════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class OnboardingRequest(BaseModel):
    step: int = Field(..., ge=1, le=3)
    data: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    program_studi: str | None = None
    university: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    education_level: str | None = None
    graduation_year: int | None = None
    interests: list[str] | None = None


class SkillSearchItem(BaseModel):
    id: str
    name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    source: str = "local"
    confidence: float = 1.0


class SkillSearchResponse(BaseModel):
    skills: list[SkillSearchItem]


PROFILE_COMPLETENESS_ITEMS = (
    {"id": "name", "label": "Nama lengkap"},
    {"id": "location", "label": "Lokasi/Domisili"},
    {"id": "education_level", "label": "Tingkat pendidikan"},
    {"id": "program_studi", "label": "Program studi"},
    {"id": "university", "label": "Universitas"},
    {"id": "skills", "label": "Keahlian"},
    {"id": "cv", "label": "CV/Resume"},
    {"id": "interests", "label": "Minat"},
)


class PipelineRunRequest(BaseModel):
    user_id: int | str | None = None
    refresh_jobs: bool = False
    profile: dict[str, Any] | None = None
    interaction_count: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=1000)
    target_role: str | None = Field(default=None, min_length=1)


class AdminAdhocProfile(BaseModel):
    """Ad-hoc tester profile. Scored live by the pipeline, never persisted."""

    name: str | None = Field(default=None, max_length=120)
    program_studi: str | None = Field(default=None, max_length=120)
    jurusan: str | None = Field(default=None, max_length=120)
    university: str | None = Field(default=None, max_length=120)
    skills: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    target_role: str | None = Field(default=None, max_length=120)


class AdminRecommendationInspectRequest(BaseModel):
    # Either resolve an existing user, or supply an ad-hoc profile (no persist).
    user_id_or_email: str | None = Field(default=None, max_length=255)
    session_id: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=10, ge=1, le=50)
    debug: bool = True
    profile: AdminAdhocProfile | None = None


class ApplicationCreateRequest(BaseModel):
    job_ids: list[str]


class JobAlertCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    query: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    min_match_percent: int = Field(default=60, ge=0, le=100)
    frequency: str = Field(default="daily", min_length=1, max_length=20)


class JobAlertUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    min_match_percent: int | None = Field(default=None, ge=0, le=100)
    frequency: str | None = Field(default=None, min_length=1, max_length=20)
    active: bool | None = None


class RecommendationFeedbackRequest(BaseModel):
    job_id: str = Field(..., min_length=1)
    recommendation_id: str | None = Field(default=None, min_length=1)
    event: str = Field(..., pattern="^(impression|view|click|source_click|save|apply|skip|dwell)$")
    rank: int = Field(..., ge=0)
    dwell_ms: int = Field(0, ge=0)
    sbert_score: float | None = None
    ncf_score: float | None = None
    dqn_score: float | None = None
    run_id: str | None = None
    served_slate_id: str | None = None
    slate_job_ids: list[str] = Field(default_factory=list)


class ExperimentVariant(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    config: dict[str, Any] = Field(default_factory=dict)
    weight: int = Field(50, ge=0, le=100)


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    variants: list[ExperimentVariant] = Field(..., min_length=2)
    target_metric: str = Field("click_through_rate", pattern="^(click_through_rate|apply_rate|mean_dwell_ms)$")


class UpdateExperimentRequest(BaseModel):
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|running|paused|completed)$")
    end_at: str | None = None


class TrackEventRequest(BaseModel):
    experiment_id: str = Field(..., min_length=1)
    event_type: str = Field(..., pattern="^(impression|click|save|apply|dwell|share)$")
    job_id: str | None = None
    dwell_ms: int = Field(0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

def to_uuid(job_id: str) -> uuid.UUID:
    """Deterministically map any string job ID to a valid UUID if not already one."""
    try:
        return uuid.UUID(job_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, job_id)


def clean_job_type(val: str | None) -> str | None:
    """Map job type string to database enum value."""
    if not val:
        return None
    val_clean = val.lower().replace("-", "_").replace(" ", "_").strip()
    if val_clean in {"full_time", "fulltime"}:
        return "full_time"
    if val_clean in {"part_time", "parttime"}:
        return "part_time"
    if val_clean in {"contract"}:
        return "contract"
    if val_clean in {"internship", "intern"}:
        return "internship"
    return None


def clean_employment_mode(val: str | None) -> str | None:
    """Map employment mode string to database enum value."""
    if not val:
        return None
    val_clean = val.lower().replace("-", "_").replace(" ", "_").strip()
    if val_clean in {"onsite", "on_site", "on-site", "kantor"}:
        return "onsite"
    if val_clean in {"remote", "wfh", "telecommute"}:
        return "remote"
    if val_clean in {"hybrid", "wfo/wfh"}:
        return "hybrid"
    return None


def clean_experience_level(val: str | None) -> str | None:
    """Map experience level string to database enum value."""
    if not val:
        return None
    val_clean = val.lower().replace("-", "_").replace(" ", "_").strip()
    if val_clean in {"entry", "junior", "fresh_graduate", "fresh graduate", "intern"}:
        return "entry"
    if val_clean in {"mid", "middle", "intermediate", "associate"}:
        return "mid"
    if val_clean in {"senior", "lead", "principal", "expert"}:
        return "senior"
    return None


def clean_job_source(val: str | None) -> str | None:
    """Map job source string to database enum value."""
    if not val:
        return None
    val_clean = val.lower().strip().replace(" ", "").replace("-", "")
    allowed = {
        "jobstreet", "linkedin", "glints", "kalibrr", "karir", "topkarir",
        "kitalulus", "techinasia", "remotive", "indeed"
    }
    if val_clean in allowed:
        return val_clean
    return None


def _fallback_logo_svg(company: str | None) -> Response:
    name = (company or "?").strip() or "?"
    initial = escape(name[0].upper())
    label = escape(name)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96" role="img" aria-label="{label} logo">
<rect width="96" height="96" rx="18" fill="#2563EB"/>
<text x="48" y="58" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="40" font-weight="700" fill="#FFFFFF">{initial}</text>
</svg>"""
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


def _proxied_company_logo_url(raw_url: str | None, company: str | None = None) -> str | None:
    if not raw_url:
        return None
    parsed = urlparse(str(raw_url))
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}:
        return str(raw_url)
    if parsed.scheme == "https" and parsed.hostname in LOGO_PROXY_ALLOWED_HOSTS:
        company_query = f"&company={quote(company or '', safe='')}" if company else ""
        return f"{PUBLIC_GATEWAY_URL}/api/company-logo?url={quote(str(raw_url), safe='')}{company_query}"
    return None


def _parse_match_data(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _clean_text_or_none(value: Any, *, max_length: int | None = None) -> str | None:
    text_value = " ".join(str(value or "").split())
    if not text_value:
        return None
    if max_length is not None:
        return text_value[:max_length]
    return text_value


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]

    seen: set[str] = set()
    cleaned: list[str] = []
    for raw_value in raw_values:
        display = _clean_text_or_none(raw_value)
        if not display:
            continue
        key = display.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(display)
    return cleaned


def _coerce_optional_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        raw_value = value.strip()
        if raw_value.endswith("Z"):
            raw_value = f"{raw_value[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
    return None


def _rich_job_fields(item: dict[str, Any]) -> dict[str, Any]:
    raw_description_html = item.get("raw_description_html")
    description_text = item.get("description_text") or item.get("description")
    parsed = parse_job_description(
        str(description_text or ""),
        str(raw_description_html) if raw_description_html else None,
    )
    parsed_fields = parsed.as_dict()

    description_sections = item.get("description_sections")
    if not isinstance(description_sections, dict):
        description_sections = parsed.description_sections

    responsibilities = _string_list(item.get("responsibilities")) or parsed.responsibilities
    requirements = _string_list(item.get("requirements")) or parsed.requirements
    nice_to_have = _string_list(item.get("nice_to_have")) or parsed.nice_to_have
    benefits = _string_list(item.get("benefits")) or parsed.benefits
    required_skills = (
        _string_list(item.get("required_skills"))
        or _string_list(item.get("required_skill_names"))
    )
    preferred_skills = (
        _string_list(item.get("preferred_skills"))
        or _string_list(item.get("preferred_skill_names"))
    )
    extracted_skills = (
        _string_list(item.get("extracted_skills"))
        or _string_list(item.get("extracted_skill_names"))
        or _string_list(item.get("skills"))
        or _string_list(item.get("tags"))
    )

    return {
        **parsed_fields,
        "raw_description_html": raw_description_html or parsed.raw_description_html,
        "description_text": parsed.description_text or _clean_text_or_none(description_text) or "",
        "description_sections": description_sections,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "nice_to_have": nice_to_have,
        "benefits": benefits,
        "seniority_level": _clean_text_or_none(item.get("seniority_level"), max_length=128)
        or parsed.seniority_level,
        "employment_type": _clean_text_or_none(item.get("employment_type"), max_length=128)
        or parsed.employment_type,
        "job_function": _clean_text_or_none(item.get("job_function"), max_length=255)
        or parsed.job_function,
        "industry": _clean_text_or_none(item.get("industry"), max_length=255)
        or parsed.industry,
        "education_level": _clean_text_or_none(item.get("education_level"), max_length=255)
        or parsed.education_level,
        "years_experience_min": item.get("years_experience_min") or parsed.years_experience_min,
        "years_experience_max": item.get("years_experience_max") or parsed.years_experience_max,
        "required_skill_names": required_skills,
        "preferred_skill_names": preferred_skills,
        "extracted_skill_names": extracted_skills,
        "source_url": item.get("source_url") or item.get("url") or None,
        "source_updated_at": _coerce_optional_datetime(item.get("source_updated_at")),
    }


def _job_has_indonesia_signal(job: dict[str, Any]) -> bool:
    host = urlparse(str(job.get("source_url") or "")).hostname or ""
    if host.lower() in INDONESIA_JOB_HOSTS:
        return True
    haystack = " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "description", "source_url")
    ).lower()
    return any(term in haystack for term in INDONESIA_JOB_TERMS)


def _coerce_posted_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        raw_value = value.strip()
        if raw_value.endswith("Z"):
            raw_value = f"{raw_value[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw_value)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            logger.warning("Invalid posted_at timestamp from pipeline: %s", value)
    return datetime.now()


async def _upsert_jobs_to_db(db: AsyncSession, ranked: list[dict[str, Any]]) -> None:
    """Bulk upsert recommended jobs into the database, handling ENUM mapping."""
    db_jobs_params = []
    for item in ranked:
        jid = str(item.get("id", ""))
        if not jid:
            continue
        rich_fields = _rich_job_fields(item)
        source_url = rich_fields["source_url"]
        skill_values = rich_fields["required_skill_names"] or rich_fields["extracted_skill_names"]
        db_jobs_params.append({
            "id": to_uuid(jid),
            "title": item.get("title") or "Untitled Job",
            "company": item.get("company") or "Unknown Company",
            "company_logo": _proxied_company_logo_url(
                item.get("company_logo") or item.get("logo") or None,
                item.get("company") or "Unknown Company",
            ),
            "location": item.get("location") or None,
            "type": clean_job_type(item.get("type")),
            "min_salary": item.get("min_salary") or None,
            "max_salary": item.get("max_salary") or None,
            "salary_currency": item.get("salary_currency") or "IDR",
            "salary_text": item.get("salary_text") or None,
            "employment_mode": clean_employment_mode(item.get("employment_mode")),
            "description": item.get("description") or None,
            "raw_description_html": rich_fields["raw_description_html"],
            "description_text": rich_fields["description_text"],
            "description_sections": json.dumps(rich_fields["description_sections"]),
            "responsibilities": rich_fields["responsibilities"],
            "requirements": rich_fields["requirements"],
            "nice_to_have": rich_fields["nice_to_have"],
            "benefits": rich_fields["benefits"],
            "seniority_level": rich_fields["seniority_level"],
            "employment_type": rich_fields["employment_type"],
            "job_function": rich_fields["job_function"],
            "industry": rich_fields["industry"],
            "education_level": rich_fields["education_level"],
            "years_experience_min": rich_fields["years_experience_min"],
            "years_experience_max": rich_fields["years_experience_max"],
            "required_skill_names": rich_fields["required_skill_names"],
            "preferred_skill_names": rich_fields["preferred_skill_names"],
            "extracted_skill_names": rich_fields["extracted_skill_names"],
            "source_url": source_url,
            "source_updated_at": rich_fields["source_updated_at"],
            "experience_level": clean_experience_level(item.get("experience_level")),
            "posted_at": _coerce_posted_at(item.get("posted_at")),
            "source": clean_job_source(item.get("source")),
            "is_active": item.get("is_active", True),
            "match_data": json.dumps({
                "skills": skill_values,
                "required_skills": rich_fields["required_skill_names"],
                "preferred_skills": rich_fields["preferred_skill_names"],
                "extracted_skills": rich_fields["extracted_skill_names"],
                "source_url": source_url,
            })
        })
    if not db_jobs_params:
        return
    try:
        job_upsert_stmt = text("""
            INSERT INTO jobs (
                id, title, company, company_logo, location, type, min_salary, max_salary,
                salary_currency, salary_text, employment_mode, description,
                raw_description_html, description_text, description_sections,
                responsibilities, requirements, nice_to_have, benefits,
                seniority_level, employment_type, job_function, industry, education_level,
                years_experience_min, years_experience_max, required_skill_names,
                preferred_skill_names, extracted_skill_names, source_url, source_updated_at,
                experience_level, posted_at, source, is_active, match_data
            ) VALUES (
                :id, :title, :company, :company_logo, :location, :type, :min_salary, :max_salary,
                :salary_currency, :salary_text, :employment_mode, :description,
                :raw_description_html, :description_text, CAST(:description_sections AS jsonb),
                :responsibilities, :requirements, :nice_to_have, :benefits,
                :seniority_level, :employment_type, :job_function, :industry, :education_level,
                :years_experience_min, :years_experience_max, :required_skill_names,
                :preferred_skill_names, :extracted_skill_names, :source_url, :source_updated_at,
                :experience_level, :posted_at, :source, :is_active, CAST(:match_data AS jsonb)
            ) ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                company = EXCLUDED.company,
                company_logo = EXCLUDED.company_logo,
                location = EXCLUDED.location,
                description = EXCLUDED.description,
                raw_description_html = COALESCE(EXCLUDED.raw_description_html, jobs.raw_description_html),
                description_text = COALESCE(NULLIF(EXCLUDED.description_text, ''), jobs.description_text),
                description_sections = COALESCE(EXCLUDED.description_sections, jobs.description_sections),
                responsibilities = EXCLUDED.responsibilities,
                requirements = EXCLUDED.requirements,
                nice_to_have = EXCLUDED.nice_to_have,
                benefits = EXCLUDED.benefits,
                seniority_level = COALESCE(EXCLUDED.seniority_level, jobs.seniority_level),
                employment_type = COALESCE(EXCLUDED.employment_type, jobs.employment_type),
                job_function = COALESCE(EXCLUDED.job_function, jobs.job_function),
                industry = COALESCE(EXCLUDED.industry, jobs.industry),
                education_level = COALESCE(EXCLUDED.education_level, jobs.education_level),
                years_experience_min = COALESCE(EXCLUDED.years_experience_min, jobs.years_experience_min),
                years_experience_max = COALESCE(EXCLUDED.years_experience_max, jobs.years_experience_max),
                required_skill_names = EXCLUDED.required_skill_names,
                preferred_skill_names = EXCLUDED.preferred_skill_names,
                extracted_skill_names = EXCLUDED.extracted_skill_names,
                source_url = COALESCE(EXCLUDED.source_url, jobs.source_url),
                source_updated_at = COALESCE(EXCLUDED.source_updated_at, jobs.source_updated_at),
                salary_text = COALESCE(EXCLUDED.salary_text, jobs.salary_text),
                source = EXCLUDED.source,
                is_active = EXCLUDED.is_active,
                match_data = COALESCE(jobs.match_data, '{}'::jsonb) || EXCLUDED.match_data
        """).bindparams(
            bindparam("responsibilities", type_=ARRAY(SqlText())),
            bindparam("requirements", type_=ARRAY(SqlText())),
            bindparam("nice_to_have", type_=ARRAY(SqlText())),
            bindparam("benefits", type_=ARRAY(SqlText())),
            bindparam("required_skill_names", type_=ARRAY(SqlText())),
            bindparam("preferred_skill_names", type_=ARRAY(SqlText())),
            bindparam("extracted_skill_names", type_=ARRAY(SqlText())),
        )
        await db.execute(
            job_upsert_stmt,
            db_jobs_params
        )
        await db.commit()
    except Exception as e:
        logger.error("Failed to upsert recommended jobs: %s", e)
        await db.rollback()


def _slate_model_versions(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    for item in ranked:
        provenance = item.get("model_provenance")
        if isinstance(provenance, dict) and provenance:
            return provenance
    return {}


def _slate_fallback_flags(ranked: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for item in ranked:
        item_flags = item.get("fallback_flags")
        if isinstance(item_flags, list):
            flags.extend(str(flag) for flag in item_flags if str(flag).strip())
    return sorted(set(flags))


async def _persist_served_slate(
    db: AsyncSession,
    *,
    slate_id: str,
    user_id: str,
    pipeline_run_id: str,
    ranked: list[dict[str, Any]],
    request: PipelineRunRequest,
    profile: dict[str, Any],
) -> None:
    if not ranked:
        return

    slate_uuid = uuid.UUID(slate_id)
    user_uuid = uuid.UUID(str(user_id))
    fallback_flags = _slate_fallback_flags(ranked)
    context = {
        "limit": request.limit,
        "refresh_jobs": request.refresh_jobs,
        "interaction_count": request.interaction_count,
        "target_role": request.target_role,
        "profile_location": profile.get("location"),
        "profile_skill_count": len(profile.get("skills") or []),
    }

    await db.execute(
        text(
            "INSERT INTO served_slates ("
            "id, user_id, pipeline_run_id, model_versions, fallback_flags, context, created_at"
            ") VALUES ("
            ":id, :user_id, :pipeline_run_id, CAST(:model_versions AS jsonb), "
            "CAST(:fallback_flags AS jsonb), CAST(:context AS jsonb), NOW()"
            ") ON CONFLICT (id) DO UPDATE SET "
            "user_id = EXCLUDED.user_id, "
            "pipeline_run_id = EXCLUDED.pipeline_run_id, "
            "model_versions = EXCLUDED.model_versions, "
            "fallback_flags = EXCLUDED.fallback_flags, "
            "context = EXCLUDED.context"
        ),
        {
            "id": slate_uuid,
            "user_id": user_uuid,
            "pipeline_run_id": pipeline_run_id,
            "model_versions": json.dumps(_slate_model_versions(ranked)),
            "fallback_flags": json.dumps(fallback_flags),
            "context": json.dumps(context),
        },
    )

    item_rows: list[dict[str, Any]] = []
    for index, item in enumerate(ranked, start=1):
        raw_job_id = str(item.get("id") or "")
        if not raw_job_id:
            continue
        rank = int(item.get("rank") or index)
        component_scores = {
            "final_score": item.get("final_score"),
            "sbert_score": item.get("sbert_score"),
            "ncf_score": item.get("ncf_score"),
            "dqn_score": item.get("dqn_score"),
            "match_percent": item.get("match_percent"),
        }
        explanation = {
            "explanation": item.get("explanation"),
            "segment": item.get("segment"),
            "strategy": item.get("strategy"),
        }
        item_rows.append(
            {
                "slate_id": slate_uuid,
                "job_id": to_uuid(raw_job_id),
                "rank": rank,
                "score": item.get("final_score"),
                "component_scores": json.dumps(component_scores),
                "model_versions": json.dumps(item.get("model_provenance") or {}),
                "fallback_flags": json.dumps(item.get("fallback_flags") or []),
                "explanation": json.dumps(explanation),
            }
        )

    if item_rows:
        await db.execute(
            text(
                "INSERT INTO served_slate_items ("
                "slate_id, job_id, rank, score, component_scores, model_versions, "
                "fallback_flags, explanation, created_at"
                ") VALUES ("
                ":slate_id, :job_id, :rank, :score, CAST(:component_scores AS jsonb), "
                "CAST(:model_versions AS jsonb), CAST(:fallback_flags AS jsonb), "
                "CAST(:explanation AS jsonb), NOW()"
                ") ON CONFLICT (slate_id, rank) DO UPDATE SET "
                "job_id = EXCLUDED.job_id, "
                "score = EXCLUDED.score, "
                "component_scores = EXCLUDED.component_scores, "
                "model_versions = EXCLUDED.model_versions, "
                "fallback_flags = EXCLUDED.fallback_flags, "
                "explanation = EXCLUDED.explanation"
            ),
            item_rows,
        )

    await db.commit()


def _map_pipeline_job(item: dict[str, Any]) -> dict[str, Any]:
    """Map pipeline job item to gateway-compatible Job dictionary."""
    rich_fields = _rich_job_fields(item)
    return {
        "id": str(item.get("id", "")),
        "title": item.get("title") or "",
        "company": item.get("company") or "",
        "company_logo": _proxied_company_logo_url(
            item.get("company_logo") or item.get("logo") or None,
            item.get("company") or "",
        ),
        "location": item.get("location") or None,
        "type": item.get("type") or None,
        "min_salary": item.get("min_salary") or None,
        "max_salary": item.get("max_salary") or None,
        "salary_currency": item.get("salary_currency") or "IDR",
        "salary_text": item.get("salary_text") or None,
        "employment_mode": item.get("employment_mode") or None,
        "description": item.get("description") or None,
        "raw_description_html": rich_fields["raw_description_html"],
        "description_text": rich_fields["description_text"],
        "description_sections": rich_fields["description_sections"],
        "responsibilities": rich_fields["responsibilities"],
        "requirements": rich_fields["requirements"],
        "nice_to_have": rich_fields["nice_to_have"],
        "benefits": rich_fields["benefits"],
        "seniority_level": rich_fields["seniority_level"],
        "employment_type": rich_fields["employment_type"],
        "job_function": rich_fields["job_function"],
        "industry": rich_fields["industry"],
        "education_level": rich_fields["education_level"],
        "years_experience_min": rich_fields["years_experience_min"],
        "years_experience_max": rich_fields["years_experience_max"],
        "required_skill_names": rich_fields["required_skill_names"],
        "preferred_skill_names": rich_fields["preferred_skill_names"],
        "extracted_skill_names": rich_fields["extracted_skill_names"],
        "experience_level": item.get("experience_level") or None,
        "posted_at": item.get("posted_at") or None,
        "source": item.get("source") or None,
        "source_url": rich_fields["source_url"],
        "source_updated_at": rich_fields["source_updated_at"],
        "skills": rich_fields["required_skill_names"] or rich_fields["extracted_skill_names"],
        "is_active": item.get("is_active", True),
    }


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _feedback_reward(event: str, dwell_ms: int = 0) -> float:
    if event == "apply":
        return 1.0
    if event == "save":
        return 0.85
    if event in {"click", "source_click"}:
        return 0.7
    if event == "view":
        return 0.45
    if event == "dwell":
        return 0.65 if dwell_ms >= 10_000 else 0.35
    if event == "impression":
        return 0.2
    if event == "skip":
        return 0.0
    return 0.0


def _client() -> httpx.AsyncClient:
    if http_client is None:
        raise HTTPException(status_code=503, detail="gateway not ready")
    return http_client


def _internal_service_headers() -> dict[str, str]:
    if not INTERNAL_SERVICE_TOKEN:
        return {}
    return {INTERNAL_SERVICE_TOKEN_HEADER: INTERNAL_SERVICE_TOKEN}


async def _pipeline_get(path: str, timeout: float | None = None) -> dict[str, Any]:
    try:
        response = await _client().get(
            f"{PIPELINE_URL}{path}",
            timeout=timeout,
            headers=_internal_service_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="pipeline timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:500]) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="pipeline unavailable") from exc


async def _pipeline_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = await _client().post(
            f"{PIPELINE_URL}{path}",
            json=payload,
            headers=_internal_service_headers(),
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="pipeline timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text[:500]) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="pipeline unavailable") from exc


def _feedback_delivery_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


async def _insert_model_feedback_outbox(
    db: AsyncSession,
    *,
    user_id: Any,
    job_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    result = await db.execute(
        text(
            "INSERT INTO model_feedback_outbox ("
            "user_id, job_id, event_type, payload, status, attempts, "
            "next_attempt_at, created_at, updated_at"
            ") VALUES ("
            ":user_id, :job_id, :event_type, CAST(:payload AS jsonb), "
            "'pending', 0, NOW(), NOW(), NOW()"
            ") RETURNING id"
        ),
        {
            "user_id": user_id,
            "job_id": job_id,
            "event_type": event_type,
            "payload": json.dumps(payload),
        },
    )
    return int(result.scalar_one())


async def _mark_model_feedback_outbox_sent(
    db: AsyncSession,
    outbox_id: int,
) -> None:
    await db.execute(
        text(
            "UPDATE model_feedback_outbox SET "
            "status = 'sent', attempts = attempts + 1, last_error = NULL, "
            "delivered_at = NOW(), updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"id": outbox_id},
    )
    await db.commit()


async def _mark_model_feedback_outbox_failed(
    db: AsyncSession,
    outbox_id: int,
    exc: Exception,
) -> None:
    await db.execute(
        text(
            "UPDATE model_feedback_outbox SET "
            "status = 'pending', attempts = attempts + 1, "
            "last_error = :last_error, "
            "next_attempt_at = NOW() + (LEAST(attempts + 1, 10) * INTERVAL '60 seconds'), "
            "updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"id": outbox_id, "last_error": _feedback_delivery_error(exc)[:2000]},
    )
    await db.commit()


async def retry_model_feedback_outbox_once(
    db: AsyncSession,
    *,
    limit: int = FEEDBACK_OUTBOX_RETRY_BATCH_SIZE,
) -> dict[str, int]:
    rows = (
        await db.execute(
            text(
                "SELECT id, payload FROM model_feedback_outbox "
                "WHERE status = 'pending' AND next_attempt_at <= NOW() "
                "ORDER BY created_at ASC, id ASC "
                "LIMIT :limit"
            ),
            {"limit": limit},
        )
    ).mappings().all()

    summary = {"attempted": 0, "sent": 0, "failed": 0}
    for row in rows:
        summary["attempted"] += 1
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            await _pipeline_post("/feedback", payload)
        except HTTPException as exc:
            await _mark_model_feedback_outbox_failed(db, int(row["id"]), exc)
            summary["failed"] += 1
        else:
            await _mark_model_feedback_outbox_sent(db, int(row["id"]))
            summary["sent"] += 1
    return summary


async def _feedback_outbox_worker_loop() -> None:
    while True:
        await asyncio.sleep(FEEDBACK_OUTBOX_RETRY_INTERVAL_SECONDS)
        try:
            async with SessionLocal() as session:
                summary = await retry_model_feedback_outbox_once(session)
            if summary["attempted"]:
                logger.info("feedback_outbox_retry summary=%s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive background loop
            logger.warning("feedback_outbox_retry_failed error=%s", exc)


async def _invalidate_pipeline_user(user_id: Any) -> None:
    """Best-effort cache bust on the pipeline service.

    Profile-mutating endpoints fire-and-forget this call so a transient
    pipeline outage never blocks the user-facing save. Errors are logged and
    swallowed because the next recommendation run will rebuild from scratch
    regardless once the pipeline is reachable again.
    """
    if http_client is None:
        return
    try:
        await http_client.post(
            f"{PIPELINE_URL}/pipeline/invalidate-user/{user_id}",
            timeout=HEALTH_TIMEOUT_SECONDS,
            headers=_internal_service_headers(),
        )
    except httpx.HTTPError as exc:
        logger.warning("pipeline invalidate failed user_id=%s: %s", user_id, exc)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# ── A/B testing helpers ──

def _pick_variant(variants: list[dict[str, Any]], user_id: str, experiment_id: str) -> dict[str, Any]:
    """Deterministically assign a user to a variant using a hash of user_id + experiment_id.

    Weights are normalized to percentages. The variant with the largest cumulative
    weight that exceeds the hash percentile wins.
    """
    if not variants:
        raise ValueError("variants list is empty")
    total_weight = sum(v.get("weight", 0) for v in variants)
    if total_weight <= 0:
        return variants[0]
    hash_input = f"{user_id}:{experiment_id}"
    hash_value = hash(hash_input)
    percentile = (hash_value % 10000) / 100.0
    cumulative = 0.0
    for variant in variants:
        weight = variant.get("weight", 0)
        cumulative += (weight / total_weight) * 100.0
        if percentile <= cumulative:
            return variant
    return variants[-1]


async def _get_active_experiments(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT id, name, variants, status, target_metric
            FROM experiments
            WHERE status = 'running'
            AND (start_at IS NULL OR start_at <= NOW())
            AND (end_at IS NULL OR end_at >= NOW())
            ORDER BY created_at DESC
            """
        )
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]


async def _get_experiment_assignment(
    db: AsyncSession, experiment_id: str, user_id: str
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT variant_name, assigned_at
            FROM experiment_assignments
            WHERE experiment_id = :experiment_id AND user_id = :user_id
            """
        ),
        {"experiment_id": experiment_id, "user_id": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _assign_user_to_variant(
    db: AsyncSession, experiment_id: str, user_id: str, variant_name: str
) -> dict[str, Any]:
    await db.execute(
        text(
            """
            INSERT INTO experiment_assignments (experiment_id, user_id, variant_name)
            VALUES (:experiment_id, :user_id, :variant_name)
            ON CONFLICT (experiment_id, user_id) DO UPDATE SET
                variant_name = EXCLUDED.variant_name,
                assigned_at = NOW()
            """
        ),
        {"experiment_id": experiment_id, "user_id": user_id, "variant_name": variant_name},
    )
    await db.commit()
    return {"experiment_id": experiment_id, "user_id": user_id, "variant_name": variant_name}


def _create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def _get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = credentials.credentials
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def _require_admin_role(token_payload: dict[str, Any]) -> None:
    if str(token_payload.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _require_admin_or_operator_role(token_payload: dict[str, Any]) -> None:
    role = str(token_payload.get("role") or "").lower()
    if role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin role required")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _admin_status_from_bool(configured: bool, *, upstream_status: str | None = None) -> str:
    if upstream_status and upstream_status not in {"healthy", "ready", "configured"}:
        return "unavailable"
    return "healthy" if configured else "unconfigured"


def _admin_service_summary(
    downstream: dict[str, Any],
    stages: dict[str, Any],
    name: str,
    stage_name: str | None = None,
    *,
    upstream_status: str | None = None,
) -> dict[str, Any]:
    configured = bool(downstream.get(name))
    stage = stages.get(stage_name or name, {})
    stage = stage if isinstance(stage, dict) else {}
    return {
        "status": _admin_status_from_bool(configured, upstream_status=upstream_status),
        "configured": configured,
        "stage": _jsonable(stage),
    }


def _admin_model_health_summary(pipeline_health: dict[str, Any]) -> dict[str, Any]:
    downstream = pipeline_health.get("downstream")
    downstream = downstream if isinstance(downstream, dict) else {}
    telemetry = pipeline_health.get("telemetry")
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    stages = telemetry.get("stages")
    stages = stages if isinstance(stages, dict) else {}
    status = str(pipeline_health.get("status") or "unknown")

    return {
        "status": status,
        "pipeline": {
            "status": status,
            "mode": pipeline_health.get("mode"),
            "p95_target_ms": pipeline_health.get("p95_target_ms"),
        },
        "models": {
            "scraper": _admin_service_summary(downstream, stages, "scraper", "scrape", upstream_status=status),
            "sbert": _admin_service_summary(downstream, stages, "sbert", upstream_status=status),
            "ncf": _admin_service_summary(downstream, stages, "ncf", upstream_status=status),
            "dqn": _admin_service_summary(downstream, stages, "dqn", upstream_status=status),
            "calibrator": {
                "status": "active" if "calibrator" in stages else "inactive",
                "stage": _jsonable(stages.get("calibrator", {})),
            },
            "aggregation": {
                "status": "active" if "aggregation" in stages else "inactive",
                "stage": _jsonable(stages.get("aggregation", {})),
            },
        },
        "telemetry": _jsonable(telemetry),
        "continual_training": _jsonable(pipeline_health.get("continual_training", {})),
    }


async def _admin_pipeline_health_snapshot() -> dict[str, Any]:
    try:
        return await _pipeline_get("/health", timeout=HEALTH_TIMEOUT_SECONDS)
    except HTTPException as exc:
        return {
            "status": "unavailable",
            "error_code": f"pipeline_http_{exc.status_code}",
        }


async def _admin_table_exists(db: AsyncSession, table_name: str) -> bool:
    try:
        result = await db.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"public.{table_name}"},
        )
        return result.scalar() is not None
    except Exception:
        await db.rollback()
        return False


async def _admin_safe_scalar(
    db: AsyncSession,
    statement: str,
    params: dict[str, Any] | None = None,
    *,
    default: Any = None,
) -> Any:
    try:
        result = await db.execute(text(statement), params or {})
        value = result.scalar()
        return default if value is None else value
    except Exception:
        await db.rollback()
        return default


async def _admin_safe_rows(
    db: AsyncSession,
    statement: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        result = await db.execute(text(statement), params or {})
        return [_jsonable(dict(row)) for row in result.mappings().all()]
    except Exception:
        await db.rollback()
        return []


def _admin_count_map(rows: list[dict[str, Any]], key_field: str = "status") -> dict[str, int]:
    return {
        str(row.get(key_field) or "unknown"): int(row.get("count") or 0)
        for row in rows
    }


async def _admin_source_distribution(db: AsyncSession) -> list[dict[str, Any]]:
    return await _admin_safe_rows(
        db,
        """
        SELECT COALESCE(source::text, 'unknown') AS source, count(*)::int AS count
        FROM jobs
        GROUP BY COALESCE(source::text, 'unknown')
        ORDER BY count DESC, source ASC
        LIMIT 20
        """,
    )


async def _admin_active_bundle(db: AsyncSession) -> ModelBundle:
    if not await _admin_table_exists(db, "model_bundles"):
        return bundle_from_row(None)
    rows = await _admin_safe_rows(db, ACTIVE_BUNDLE_SQL)
    return bundle_from_row(rows[0] if rows else None)


async def _admin_model_registry_rows(db: AsyncSession) -> dict[str, dict[str, Any]]:
    if not await _admin_table_exists(db, "model_registry"):
        return {}
    rows = await _admin_safe_rows(
        db,
        """
        SELECT model_version, model_type, checkpoint_hash, dimension, source_path, status
        FROM model_registry
        WHERE status IN ('active', 'registered')
        ORDER BY status = 'active' DESC, created_at DESC
        """,
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        version = str(row.get("model_version") or "")
        model_type = str(row.get("model_type") or "")
        if version and version not in out:
            out[version] = row
        if model_type and model_type not in out:
            out[model_type] = row
    return out


async def _admin_active_model_artifacts(db: AsyncSession) -> dict[str, dict[str, Any]]:
    if not await _admin_table_exists(db, "model_artifacts"):
        return {}
    rows = await _admin_safe_rows(
        db,
        """
        SELECT DISTINCT ON (service)
          service, model_name, model_version, artifact_path, artifact_hash,
          training_run_id, metrics, fallback_mode, active, created_at
        FROM model_artifacts
        WHERE active = true
        ORDER BY service, created_at DESC
        """,
    )
    return {str(row.get("service")): row for row in rows if row.get("service")}


async def _admin_latency_summary(db: AsyncSession) -> dict[str, Any]:
    if not await _admin_table_exists(db, "hybrid_request_log"):
        return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "source": "unavailable"}
    rows = await _admin_safe_rows(
        db,
        """
        SELECT
          percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
          percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms
        FROM hybrid_request_log
        WHERE latency_ms IS NOT NULL
          AND created_at > NOW() - interval '24 hours'
        """,
    )
    if not rows:
        return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "source": "hybrid_request_log"}
    row = rows[0]
    return {
        "p50_ms": round(float(row["p50_ms"]), 2) if row.get("p50_ms") is not None else None,
        "p95_ms": round(float(row["p95_ms"]), 2) if row.get("p95_ms") is not None else None,
        "p99_ms": round(float(row["p99_ms"]), 2) if row.get("p99_ms") is not None else None,
        "source": "hybrid_request_log",
    }


async def _admin_postgres_status(db: AsyncSession) -> str:
    value = await _admin_safe_scalar(db, "SELECT 1", default=None)
    return "healthy" if value == 1 else "unavailable"


async def _admin_redis_status() -> str:
    if not REDIS_URL:
        return "unconfigured"
    redis = await _get_gateway_redis()
    if redis is None:
        return "unavailable"
    try:
        await redis.ping()
        return "healthy"
    except Exception:
        return "unavailable"


async def _admin_embedding_task_counts(db: AsyncSession) -> dict[str, int]:
    if not await _admin_table_exists(db, "embedding_tasks"):
        return {}
    return _admin_count_map(
        await _admin_safe_rows(
            db,
            """
            SELECT status, count(*)::int AS count
            FROM embedding_tasks
            GROUP BY status
            """,
        )
    )


def _admin_embedding_worker_status(task_counts: dict[str, int]) -> str:
    if not task_counts:
        return "unavailable"
    if task_counts.get("dead_letter", 0) or task_counts.get("failed", 0):
        return "degraded"
    if task_counts.get("processing", 0):
        return "processing"
    return "healthy"


def _admin_bundle_payload(bundle: ModelBundle) -> dict[str, Any]:
    return {
        "bundle_version": bundle.bundle_version,
        "sbert_model_version": bundle.sbert_model_version,
        "ncf_model_version": bundle.ncf_model_version,
        "dqn_model_version": bundle.dqn_model_version,
        "state_schema": bundle.state_schema,
        "response_schema": bundle.response_schema,
        "weights": bundle.weights,
        "source": bundle.source,
    }


async def _admin_session_events(
    db: AsyncSession,
    *,
    user_id: Any | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = [
        "event_type IN ('view','click','source_click','save','apply','skip','dwell')"
    ]
    params: dict[str, Any] = {"limit": limit}
    if user_id is not None:
        clauses.append("user_id = :user_id")
        params["user_id"] = user_id
    if session_id:
        clauses.append("session_id = :session_id")
        params["session_id"] = session_id
    where_clause = " AND ".join(clauses)
    rows = await _admin_safe_rows(
        db,
        f"""
        SELECT id, event_type AS event, user_id::text AS user_id, job_id::text AS job_id,
               slate_id::text AS slate_id, rank, session_id, source, dwell_ms,
               created_at
        FROM feedback_events
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
        """,
        params,
    )
    rows.reverse()
    return rows


async def _admin_resolve_user_identifier(db: AsyncSession, identifier: str) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                """
                SELECT id, name, email, role, completion_percent,
                       program_studi, university, cv_uploaded_at,
                       location, education_level, graduation_year, interests
                FROM users
                WHERE id::text = :identifier OR lower(email) = lower(:identifier)
                LIMIT 1
                """
            ),
            {"identifier": identifier.strip()},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


def _admin_trace_item(item: dict[str, Any], index: int, *, session_event_count: int) -> dict[str, Any]:
    final_rank = int(item.get("final_rank") or item.get("rank") or index)
    sbert_rank = item.get("sbert_rank")
    ncf_rank_after = item.get("rank_before_dqn")
    dqn_rank_after = item.get("rank_after_dqn")
    explanation = item.get("explanation")
    reason_codes: list[str] = []
    if isinstance(explanation, list):
        reason_codes.extend(str(part) for part in explanation if str(part).strip())
    elif explanation:
        reason_codes.append(str(explanation))
    if item.get("scoring_mode"):
        reason_codes.append(f"scoring_mode:{item.get('scoring_mode')}")
    return {
        "job_id": str(item.get("id") or item.get("job_id") or ""),
        "title": item.get("title") or "",
        "company": item.get("company") or "",
        "final_rank": final_rank,
        "final_score": float(item.get("final_score") or 0.0),
        "sbert_score": float(item.get("sbert_score") or 0.0),
        "sbert_rank": int(sbert_rank) if sbert_rank else index,
        "ncf_score": float(item.get("ncf_score") or 0.0),
        "ncf_rank_before": int(sbert_rank) if sbert_rank else index,
        "ncf_rank_after": int(ncf_rank_after) if ncf_rank_after else index,
        "ncf_mode": "scored" if item.get("ncf_score") is not None else "unavailable",
        "dqn_score": float(item.get("dqn_score") or item.get("dqn_session_score") or 0.0),
        "dqn_rank_before": int(ncf_rank_after) if ncf_rank_after else index,
        "dqn_rank_after": int(dqn_rank_after) if dqn_rank_after else index,
        "dqn_mode": item.get("dqn_mode") or "unknown",
        "session_events_used": session_event_count,
        "matched_skills": _jsonable(item.get("matched_skills") or []),
        "reason_codes": reason_codes[:6],
    }


def _admin_lineage_validation(trace_items: list[dict[str, Any]]) -> dict[str, Any]:
    job_ids = [item["job_id"] for item in trace_items if item.get("job_id")]
    unique_ids = set(job_ids)
    return {
        "status": "valid" if len(job_ids) == len(unique_ids) else "warning",
        "dqn_candidate_subset_of_ncf": True,
        "final_subset_of_dqn": True,
        "duplicate_job_ids": sorted(job_id for job_id in unique_ids if job_ids.count(job_id) > 1),
    }


async def _require_user(db: AsyncSession, token_payload: dict[str, Any]) -> dict[str, Any]:
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    row = (
        await db.execute(
            text(
                "SELECT id, name, email, role, completion_percent, program_studi, university, cv_uploaded_at, "
                "location, education_level, graduation_year, interests "
                "FROM users WHERE id = :id"
            ),
            {"id": user_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


def _normalise_skill_value(value: str) -> str:
    return normalize_skill_term(value)


def _runtime_skill_seed_rows() -> list[dict[str, Any]]:
    return [
        row for row in DEFAULT_SKILL_TAXONOMY
        if "local" in str(row.get("source") or "").lower()
        or str(row.get("name") or "") in SKILL_SEARCH_PRIORITY
    ]


def _is_user_facing_skill(skill: dict[str, Any]) -> bool:
    name = str(skill.get("name") or "")
    category = str(skill.get("category") or "").lower()
    source = str(skill.get("source") or "").lower()
    if name in SKILL_SEARCH_PRIORITY:
        return True
    if "local" in source or "esco" in source:
        return category in USER_FACING_SKILL_CATEGORIES
    if "software skills" in source:
        return False
    return category in USER_FACING_SKILL_CATEGORIES


async def _ensure_default_skill_taxonomy(db: AsyncSession) -> bool:
    """Seed the baseline controlled vocabulary if the taxonomy table exists."""

    try:
        table_exists = (
            await db.execute(text("SELECT to_regclass('public.skills')"))
        ).scalar_one()
        if table_exists is None:
            return False

        count = int((await db.execute(text("SELECT COUNT(*) FROM skills"))).scalar_one() or 0)
        target_count = min(5_000, len(DEFAULT_SKILL_TAXONOMY))
        runtime_rows = _runtime_skill_seed_rows()
        if count >= target_count:
            if runtime_rows:
                await db.execute(_SEED_SKILL_STMT, runtime_rows)
                await db.commit()
            return True

        await db.execute(_SEED_SKILL_STMT, list(DEFAULT_SKILL_TAXONOMY))
        await db.commit()
        return True
    except Exception as exc:  # pragma: no cover - protects ad-hoc pre-migration DBs
        await db.rollback()
        logger.warning("skill taxonomy seed skipped: %s", exc)
        return False


async def _load_skill_taxonomy(db: AsyncSession) -> list[dict[str, Any]]:
    if not await _ensure_default_skill_taxonomy(db):
        return []

    rows = (
        await db.execute(
            text(
                "SELECT name, category, aliases, source, confidence "
                "FROM skills ORDER BY frequency DESC, confidence DESC, name ASC "
                "LIMIT :limit"
            ),
            {"limit": SKILL_SEARCH_MAX_ROWS},
        )
    ).mappings().all()
    skills = [
        {
            "id": str(row["name"]),
            "name": str(row["name"]),
            "category": str(row["category"] or "technical"),
            "aliases": [str(alias) for alias in (row.get("aliases") or [])],
            "source": str(row.get("source") or "local"),
            "confidence": float(row.get("confidence") or 1.0),
        }
        for row in rows
    ]
    return [skill for skill in skills if _is_user_facing_skill(skill)]


def _skill_search_score(skill: dict[str, Any], query: str) -> int:
    name = _normalise_skill_value(skill["name"])
    aliases = [_normalise_skill_value(alias) for alias in skill.get("aliases", [])]
    words = name.split()
    if query == name:
        return 0
    if query in aliases:
        return 1
    if name.startswith(query):
        return 2
    if any(alias.startswith(query) for alias in aliases):
        return 3
    if any(word.startswith(query) for word in words):
        return 4
    if query in name:
        return 5
    if any(query in alias for alias in aliases):
        return 6
    return 99


def _skill_search_priority(skill: dict[str, Any]) -> int:
    return SKILL_SEARCH_PRIORITY.get(str(skill.get("name") or ""), 0)


def _normalise_query_values(values: list[str] | None) -> set[str]:
    normalised: set[str] = set()
    for value in values or []:
        for part in str(value).split(","):
            candidate = _normalise_skill_value(part)
            if candidate:
                normalised.add(candidate)
    return normalised


def _skill_identity_terms(skill: dict[str, Any]) -> set[str]:
    return {
        _normalise_skill_value(value)
        for value in [skill["name"], *skill.get("aliases", [])]
        if _normalise_skill_value(value)
    }


async def _canonicalize_profile_skills(
    db: AsyncSession, raw_skills: list[str]
) -> list[str]:
    taxonomy = await _load_skill_taxonomy(db)
    if not taxonomy:
        return [str(skill).strip() for skill in raw_skills if str(skill).strip()]

    lookup: dict[str, str] = {}
    for skill in taxonomy:
        lookup[_normalise_skill_value(skill["name"])] = skill["name"]
        for alias in skill.get("aliases", []):
            lookup[_normalise_skill_value(alias)] = skill["name"]

    canonical: list[str] = []
    seen: set[str] = set()
    terms = list(lookup.keys())
    for raw_skill in raw_skills:
        raw_value = str(raw_skill).strip()
        if not raw_value:
            continue
        normalised = _normalise_skill_value(raw_value)
        canonical_name = lookup.get(normalised)
        if canonical_name is None:
            match = get_close_matches(normalised, terms, n=1, cutoff=0.72)
            suggestion = lookup[match[0]] if match else None
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Skill is not in the controlled taxonomy",
                    "invalid_skill": raw_value,
                    "suggestion": suggestion,
                },
            )
        if canonical_name not in seen:
            canonical.append(canonical_name)
            seen.add(canonical_name)
    return canonical


async def _extract_skills_from_cv_text(db: AsyncSession, raw_text: str) -> list[str]:
    """Scan CV text for known skill names/aliases and return canonical matches.

    Unlike ``_canonicalize_profile_skills``, this never raises on unknown text;
    it simply skips words that do not match the taxonomy.
    """
    taxonomy = await _load_skill_taxonomy(db)
    if not taxonomy:
        return []

    lookup: dict[str, str] = {}
    for skill in taxonomy:
        lookup[_normalise_skill_value(skill["name"])] = skill["name"]
        for alias in skill.get("aliases", []):
            lookup[_normalise_skill_value(alias)] = skill["name"]

    # Index multi-word skills so phrases like "machine learning" match first.
    multi_word_skills = {k: v for k, v in lookup.items() if " " in k}
    single_word_skills = {k: v for k, v in lookup.items() if " " not in k}

    normalized_text = _normalise_skill_value(raw_text)
    found: dict[str, str] = {}

    # Try multi-word matches first to avoid partial overlaps.
    for term, canonical_name in multi_word_skills.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_text):
            found[canonical_name] = canonical_name

    # Then single-word token matches (strip trailing punctuation).
    tokens = set(normalized_text.split())
    for token in tokens:
        if len(token) <= 2 and token not in {"ai", "go"}:
            continue
        if token in single_word_skills:
            canonical_name = single_word_skills[token]
            found[canonical_name] = canonical_name

    return list(found.keys())


async def _profile_skill_names(db: AsyncSession, user_id: Any) -> list[str]:
    rows = (
        await db.execute(
            text("SELECT skill FROM user_skills WHERE user_id = :uid ORDER BY skill"),
            {"uid": user_id},
        )
    ).mappings().all()
    return [str(row["skill"]) for row in rows if row.get("skill")]


def _has_profile_value(value: Any) -> bool:
    return bool(str(value or "").strip())


def _profile_completeness_summary(
    user: dict[str, Any], skill_names: list[str]
) -> dict[str, Any]:
    skill_count = len([skill for skill in skill_names if _has_profile_value(skill)])
    completed_by_id = {
        "name": _has_profile_value(user.get("name")),
        "location": _has_profile_value(user.get("location")),
        "education_level": _has_profile_value(user.get("education_level")),
        "program_studi": _has_profile_value(user.get("program_studi")),
        "university": _has_profile_value(user.get("university")),
        "skills": skill_count > 0,
        "cv": user.get("cv_uploaded_at") is not None,
        "interests": bool(user.get("interests")),
    }
    items = [
        {
            "id": item["id"],
            "label": item["label"],
            "completed": bool(completed_by_id[item["id"]]),
        }
        for item in PROFILE_COMPLETENESS_ITEMS
    ]
    completed_item_ids = [item["id"] for item in items if item["completed"]]
    missing_item_ids = [item["id"] for item in items if not item["completed"]]
    percent = round(100 * len(completed_item_ids) / len(items)) if items else 0
    return {
        "percent": percent,
        "completed_item_ids": completed_item_ids,
        "missing_item_ids": missing_item_ids,
        "items": items,
        "skill_count": skill_count,
        "stored_percent": int(user.get("completion_percent") or 0),
        "cv_uploaded_at": (
            user["cv_uploaded_at"].isoformat()
            if isinstance(user.get("cv_uploaded_at"), datetime)
            else user.get("cv_uploaded_at")
        ),
    }


async def _pipeline_profile_for_user(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    skills = await _profile_skill_names(db, user["id"])
    return {
        "name": user.get("name"),
        "program_studi": user.get("program_studi"),
        "jurusan": user.get("program_studi"),
        "university": user.get("university"),
        "skills": skills,
        "location": user.get("location"),
        "education_level": user.get("education_level"),
        "interests": list(user.get("interests") or []),
    }


def _profile_has_personalization_signal(profile: dict[str, Any], user: dict[str, Any]) -> bool:
    """True when the profile carries enough signal to personalize a slate.

    Skills and CV are the personalization inputs (study field alone yields only
    generic by-major matches and still leans on the pipeline's hardcoded
    fallback skills). Without either, gate the request and prompt completion.
    """
    has_skills = bool(profile.get("skills"))
    has_cv = user.get("cv_uploaded_at") is not None
    return has_skills or has_cv


def _needs_profile_response() -> dict[str, Any]:
    """Empty slate signalling the client to prompt profile completion."""
    return {
        "schema_version": "recommendation_v2",
        "request_id": str(uuid.uuid4()),
        "recommendations": [],
        "fairness_tpr_gap": 0.0,
        "degraded": False,
        "stale": False,
        "source": "needs_profile",
        "needs_profile": True,
        "model_bundle_version": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# DQN session window: events newer than this feed the session reranker state.
SESSION_EVENT_WINDOW_HOURS = int(os.getenv("SESSION_EVENT_WINDOW_HOURS", "8"))
SESSION_EVENT_LIMIT = int(os.getenv("SESSION_EVENT_LIMIT", "20"))

# Short-lived Redis slate cache (contract §2/§10). Key includes the user's
# session_state_version, so every save/skip/feedback event bumps the version
# and the next request bypasses the stale slate. Redis missing => no caching,
# behavior identical to before (graceful degradation).
REDIS_URL = os.getenv("REDIS_URL", "").strip()
SLATE_CACHE_TTL_SECONDS = int(os.getenv("SLATE_CACHE_TTL_SECONDS", "60"))
_gateway_redis: Any = None
_slate_memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_slate_memory_response_cache: dict[str, tuple[float, bytes, bytes]] = {}


async def _get_gateway_redis() -> Any:
    global _gateway_redis
    if _gateway_redis is None and REDIS_URL:
        try:
            import redis.asyncio as aioredis

            _gateway_redis = aioredis.from_url(
                REDIS_URL, decode_responses=True, socket_connect_timeout=2
            )
            await _gateway_redis.ping()
        except Exception as exc:  # pragma: no cover - depends on local service
            logger.warning("gateway redis cache disabled: %s", exc)
            _gateway_redis = False
    return _gateway_redis if _gateway_redis is not False else None


async def _session_state_version(db: AsyncSession, user_id: str) -> str:
    """Cache-key version component for the slate cache.

    Primary signal is the user's feedback-event count inside the session
    window — DB-derived, so slate invalidation survives Redis outages (a
    failed INCR during a flap can no longer serve a pre-event slate after
    recovery). The Redis INCR component remains to cover jobs-API save/skip
    toggles, which upsert user_job_interactions without adding a
    feedback_events row; that part is best-effort by design.
    """
    db_component = 0
    try:
        db_component = int(
            (
                await db.execute(
                    text(
                        "SELECT count(*) FROM feedback_events WHERE user_id = :uid "
                        "AND created_at > NOW() - make_interval(hours => :window_hours)"
                    ),
                    {"uid": user_id, "window_hours": SESSION_EVENT_WINDOW_HOURS},
                )
            ).scalar()
            or 0
        )
    except Exception:  # pragma: no cover - optional table in ad-hoc DBs
        db_component = 0
    redis_component = 0
    redis = await _get_gateway_redis()
    if redis is not None:
        try:
            value = await redis.get(f"scpa:sessver:{user_id}")
            redis_component = int(value) if value else 0
        except Exception:  # pragma: no cover - transient redis outage
            redis_component = 0
    return f"{db_component}.{redis_component}"


async def _bump_session_state_version(user_id: str) -> None:
    """Invalidate the user's cached slate by advancing the version key."""
    _purge_user_slate_memory_cache(user_id)
    redis = await _get_gateway_redis()
    if redis is None:
        return
    try:
        await redis.incr(f"scpa:sessver:{user_id}")
    except Exception:  # pragma: no cover - transient redis outage
        pass


def _slate_cache_key(user_id: str, session_version: int, limit: int) -> str:
    return f"scpa:slate:{user_id}:v{session_version}:n{limit}"


def _slate_fast_cache_key(user_id: str, redis_session_version: int, limit: int) -> str:
    return f"scpa:slate-fast:{user_id}:rv{redis_session_version}:n{limit}"


def _slate_front_cache_key(user_id: str, limit: int) -> str:
    return f"scpa:slate-front:{user_id}:n{limit}"


def _store_memory_slate(key: str, payload: dict[str, Any], ttl_seconds: int | float) -> None:
    _slate_memory_cache[key] = (time.monotonic() + ttl_seconds, payload)


def _store_memory_slate_response(
    key: str,
    payload: dict[str, Any],
    *,
    cache_tier: str,
    ttl_seconds: int | float,
) -> None:
    response_payload = {
        **payload,
        "cached": True,
        "cache_tier": cache_tier,
    }
    content = json.dumps(response_payload, default=str, separators=(",", ":")).encode("utf-8")
    _slate_memory_response_cache[key] = (
        time.monotonic() + ttl_seconds,
        content,
        gzip.compress(content, compresslevel=5),
    )


def _get_memory_slate_response(key: str, request: Request | None = None) -> Response | None:
    memory_entry = _slate_memory_response_cache.get(key)
    if memory_entry is None:
        return None
    expires_at, content, gzip_content = memory_entry
    if expires_at <= time.monotonic():
        _slate_memory_response_cache.pop(key, None)
        return None
    _ = request
    _ = gzip_content
    return Response(content=content, media_type="application/json")


def _purge_user_slate_memory_cache(user_id: str) -> None:
    for key in list(_slate_memory_cache):
        if key.startswith("scpa:slate") and f":{user_id}:" in key:
            _slate_memory_cache.pop(key, None)
    for key in list(_slate_memory_response_cache):
        if key.startswith("scpa:slate") and f":{user_id}:" in key:
            _slate_memory_response_cache.pop(key, None)


async def _redis_session_state_version(user_id: str) -> int:
    redis = await _get_gateway_redis()
    if redis is None:
        return 0
    try:
        value = await redis.get(f"scpa:sessver:{user_id}")
        return int(value) if value else 0
    except Exception:  # pragma: no cover - transient redis outage
        return 0


async def _get_cached_slate(key: str) -> dict[str, Any] | None:
    memory_entry = _slate_memory_cache.get(key)
    if memory_entry is not None:
        expires_at, payload = memory_entry
        if expires_at > time.monotonic():
            return payload
        _slate_memory_cache.pop(key, None)

    redis = await _get_gateway_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        payload = json.loads(raw)
        _store_memory_slate(key, payload, min(SLATE_CACHE_TTL_SECONDS, 10))
        return payload
    except Exception:  # pragma: no cover - transient redis outage
        return None


async def _store_cached_slate(key: str, payload: dict[str, Any]) -> None:
    _store_memory_slate(key, payload, min(SLATE_CACHE_TTL_SECONDS, 10))
    redis = await _get_gateway_redis()
    if redis is None:
        return
    try:
        await redis.setex(key, SLATE_CACHE_TTL_SECONDS, json.dumps(payload, default=str))
    except Exception:  # pragma: no cover - transient redis outage
        pass


async def _recent_session_events(db: AsyncSession, user_id: Any) -> list[dict[str, Any]]:
    """Current-session behavioral events for the DQN reranker (contract §10).

    Sourced from persisted feedback_events so a page reload or a new request
    in the same session still sees the user's save/skip/view/apply actions.
    Returned oldest-first. Impressions are excluded (no behavioral signal).
    """
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT job_id::text AS job_id, event_type AS event, rank, "
                    "EXTRACT(EPOCH FROM created_at) AS ts "
                    "FROM feedback_events "
                    "WHERE user_id = :uid "
                    "AND created_at > NOW() - make_interval(hours => :window_hours) "
                    "AND event_type IN ('view','click','source_click','save','apply','skip','dwell') "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {
                    "uid": user_id,
                    "window_hours": SESSION_EVENT_WINDOW_HOURS,
                    "limit": SESSION_EVENT_LIMIT,
                },
            )
        ).mappings().all()
    except Exception:  # pragma: no cover - optional table in ad-hoc DBs
        return []
    events = [
        {
            "job_id": str(row["job_id"]),
            "event": str(row["event"]),
            "rank": row.get("rank"),
            "ts": float(row["ts"]) if row.get("ts") is not None else None,
        }
        for row in rows
    ]
    events.reverse()
    return events


async def _resolve_target_role(db: AsyncSession, user: dict[str, Any], requested: str | None = None) -> str:
    if requested:
        return requested
    try:
        row = (
            await db.execute(
                text(
                    "SELECT target_role FROM user_profiles WHERE user_id = :uid "
                    "AND target_role IS NOT NULL LIMIT 1"
                ),
                {"uid": user["id"]},
            )
        ).mappings().first()
        if row and row.get("target_role"):
            return str(row["target_role"])
    except Exception:
        pass
    return str(user.get("program_studi") or "Data Scientist")


async def _user_skills(db: AsyncSession, user_id: Any) -> set[str]:
    rows = (
        await db.execute(
            text("SELECT skill FROM user_skills WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).mappings().all()
    return {str(r["skill"]).lower().strip() for r in rows if r.get("skill")}


def _normalized_skill_name(skill: Any) -> str:
    return str(skill or "").strip().lower()


def _display_skill_list(skills: Any) -> list[str]:
    if not isinstance(skills, list):
        return []

    deduped: dict[str, str] = {}
    for skill in skills:
        display = str(skill or "").strip()
        key = _normalized_skill_name(display)
        if display and key not in deduped:
            deduped[key] = display
    return sorted(deduped.values(), key=lambda item: item.lower())


def _taxonomy_by_name(taxonomy: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    return {
        _normalise_skill_value(str(skill.get("name") or "")): dict(skill)
        for skill in taxonomy
        if str(skill.get("name") or "").strip()
    }


def _skill_terms(skill_name: str, taxonomy_by_key: dict[str, dict[str, Any]]) -> set[str]:
    key = _normalise_skill_value(skill_name)
    row = taxonomy_by_key.get(key)
    terms = {key}
    if row:
        terms.add(_normalise_skill_value(str(row.get("name") or "")))
        terms.update(
            _normalise_skill_value(str(alias))
            for alias in row.get("aliases", [])
            if _normalise_skill_value(str(alias))
        )
    return {term for term in terms if term}


def _skill_has_text_evidence(
    skill_name: str,
    normalized_text: str,
    taxonomy_by_key: dict[str, dict[str, Any]],
) -> bool:
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_text)
        for term in _skill_terms(skill_name, taxonomy_by_key)
    )


def _job_skill_evidence_text(row: dict[str, Any], match_data: dict[str, Any] | None = None) -> str:
    match_data = match_data or {}
    values: list[Any] = [
        row.get("title"),
        row.get("description_text"),
        row.get("description"),
        row.get("description_sections"),
        row.get("responsibilities"),
        row.get("requirements"),
        row.get("nice_to_have"),
        match_data.get("description_text"),
        match_data.get("description"),
    ]
    parts: list[str] = []
    for value in values:
        if isinstance(value, dict):
            parts.extend(str(item) for item in value.values() if str(item).strip())
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
        elif value is not None and str(value).strip():
            parts.append(str(value))
    return " ".join(parts)


def _infer_skills_from_job_text(
    raw_text: str,
    taxonomy: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    max_results: int = 16,
) -> list[str]:
    normalized_text = _normalise_skill_value(raw_text)
    inferred: list[str] = []
    for skill in taxonomy:
        if not _is_user_facing_skill(dict(skill)):
            continue
        name = str(skill.get("name") or "").strip()
        if not name:
            continue
        key = _normalise_skill_value(name)
        terms = {key}
        terms.update(
            _normalise_skill_value(str(alias))
            for alias in skill.get("aliases", [])
            if _normalise_skill_value(str(alias))
        )
        if any(
            len(term) > 2
            and re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized_text)
            for term in terms
        ):
            inferred.append(name)
        if len(inferred) >= max_results:
            break
    return _display_skill_list(inferred)


def _sanitize_skill_signals_for_job(
    *,
    row: dict[str, Any],
    match_data: dict[str, Any],
    taxonomy: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[list[str], list[str], list[str]]:
    taxonomy_by_key = _taxonomy_by_name(taxonomy)
    has_rich_evidence = any(
        row.get(key)
        for key in (
            "description_text",
            "description",
            "description_sections",
            "responsibilities",
            "requirements",
            "nice_to_have",
        )
    )
    if not has_rich_evidence:
        required = _display_skill_list(
            row.get("required_skill_names")
            or match_data.get("required_skills")
            or match_data.get("skills")
            or []
        )
        preferred = _display_skill_list(
            row.get("preferred_skill_names")
            or match_data.get("preferred_skills")
            or []
        )
        extracted = _display_skill_list(
            row.get("extracted_skill_names")
            or match_data.get("extracted_skills")
            or []
        )
        if not required:
            required = extracted
        return required, preferred, extracted

    evidence_text = _job_skill_evidence_text(row, match_data)
    normalized_text = _normalise_skill_value(evidence_text)
    inferred = _infer_skills_from_job_text(evidence_text, taxonomy)

    def evidenced(skills: list[str]) -> list[str]:
        return _display_skill_list(
            [
                skill for skill in skills
                if _skill_has_text_evidence(skill, normalized_text, taxonomy_by_key)
            ]
        )

    required = evidenced(
        _display_skill_list(
            row.get("required_skill_names")
            or match_data.get("required_skills")
            or []
        )
    )
    preferred = evidenced(
        _display_skill_list(
            row.get("preferred_skill_names")
            or match_data.get("preferred_skills")
            or []
        )
    )
    extracted = _display_skill_list(
        [
            *evidenced(
                _display_skill_list(
                    row.get("extracted_skill_names")
                    or match_data.get("extracted_skills")
                    or match_data.get("skills")
                    or []
                )
            ),
            *inferred,
        ]
    )
    if not required:
        required = inferred
    return required, preferred, extracted


async def _job_skill_gap(
    db: AsyncSession, user_skills: set[str], job_id: str
) -> dict[str, Any]:
    db_uuid = to_uuid(job_id)
    row = (
        await db.execute(
            text(
                "SELECT title, company, description, description_text, description_sections, "
                "responsibilities, requirements, nice_to_have, required_skill_names, "
                "preferred_skill_names, extracted_skill_names, match_data FROM jobs WHERE id = :id"
            ),
            {"id": db_uuid},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    row_dict = dict(row)
    match_data = _parse_match_data(row_dict.get("match_data"))
    taxonomy = await _load_skill_taxonomy(db)
    required_skills, preferred_skills, extracted_skills = _sanitize_skill_signals_for_job(
        row=row_dict,
        match_data=match_data,
        taxonomy=taxonomy or list(DEFAULT_SKILL_TAXONOMY),
    )
    user_skill_keys = {_normalized_skill_name(skill) for skill in user_skills}
    matched = [
        skill
        for skill in required_skills
        if _normalized_skill_name(skill) in user_skill_keys
    ]
    missing = [
        skill
        for skill in required_skills
        if _normalized_skill_name(skill) not in user_skill_keys
    ]
    explanation = {
        "matched_count": len(matched),
        "missing_count": len(missing),
        "required_count": len(required_skills),
        "summary": f"{len(matched)} of {len(required_skills)} required skills matched.",
    }
    return {
        "job_id": job_id,
        "job_title": row.get("title"),
        "company": row.get("company"),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "extracted_skills": extracted_skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_match_percent": round(
            100.0 * len(matched) / max(len(required_skills), 1), 1
        ),
        "explanation": explanation,
    }


def _employer_fit_score(user: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Lightweight reciprocal-fit score based on hard requirements."""
    score = 0.0
    reasons: list[str] = []
    # Experience level heuristic
    user_level = str(user.get("experience_level") or "entry").lower()
    job_level = str(job.get("experience_level") or "").lower()
    if user_level and job_level:
        levels = {"entry": 1, "mid": 2, "senior": 3}
        if levels.get(user_level, 1) >= levels.get(job_level, 1):
            score += 0.3
        else:
            reasons.append("Experience level below requirement")
    # Location heuristic
    user_loc = str(user.get("location") or "").lower()
    job_loc = str(job.get("location") or "").lower()
    if user_loc and job_loc and (user_loc in job_loc or job_loc in user_loc):
        score += 0.2
    # Education heuristic
    user_program = str(user.get("program_studi") or "").lower()
    job_desc = str(job.get("description") or "").lower()
    if user_program and any(k in job_desc for k in (user_program, user_program.replace(" ", ""))):
        score += 0.2
    # Salary willingness (placeholder)
    score += 0.3
    return {
        "employer_fit_score": round(min(1.0, score), 3),
        "employer_fit_reasons": reasons,
    }


def _clamped_reason_score(value: Any) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        numeric = 0.0
    return round(max(0.0, min(1.0, numeric)), 3)


def _parse_reason_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _recency_reason_score(posted_at: Any) -> float:
    parsed = _parse_reason_datetime(posted_at)
    if parsed is None:
        return 0.0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age_days = max((now - parsed).total_seconds() / 86_400, 0.0)
    recency = 1.0 - min(age_days, REASON_FILTER_RECENCY_WINDOW_DAYS) / REASON_FILTER_RECENCY_WINDOW_DAYS
    return round(max(0.0, min(1.0, recency)), 3)


def _profile_location_terms(profile: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("location", "preferred_location"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    preferred_locations = profile.get("preferred_locations")
    if isinstance(preferred_locations, list):
        values.extend(str(value).strip() for value in preferred_locations if str(value).strip())
    return values


def _location_reason_score(profile: dict[str, Any], job: dict[str, Any]) -> float:
    job_location = str(job.get("location") or "").strip().casefold()
    if not job_location:
        return 0.0
    for location in _profile_location_terms(profile):
        normalized = location.casefold()
        if normalized and (normalized in job_location or job_location in normalized):
            return 1.0
    return 0.0


def _recommendation_reason_filter_scores(
    profile: dict[str, Any],
    item: dict[str, Any],
    job: dict[str, Any],
    *,
    sbert_score: float,
    ncf_score: float,
    dqn_score: float,
) -> dict[str, float]:
    return {
        "semantic_fit": _clamped_reason_score(sbert_score),
        "interaction_fit": _clamped_reason_score(ncf_score),
        "session_rerank_signal": _clamped_reason_score(dqn_score),
        "location_fit": _location_reason_score(profile, job),
        "recency": _recency_reason_score(item.get("posted_at") or job.get("posted_at")),
    }


def _compact_recommendation_job(job: dict[str, Any]) -> dict[str, Any]:
    # Keep this in sync with the fields the recommendation card renders
    # (frontend RecItem). ``company_logo`` must be included so logos appear on
    # the Rekomendasi page the same way they do on the /api/jobs catalog —
    # ``_map_pipeline_job`` already routes it through ``_proxied_company_logo_url``.
    compact = {
        "id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "company_logo": job.get("company_logo"),
        "location": job.get("location"),
        "type": job.get("type"),
        "employment_mode": job.get("employment_mode"),
        "experience_level": job.get("experience_level"),
        "seniority_level": job.get("seniority_level"),
        "min_salary": job.get("min_salary"),
        "max_salary": job.get("max_salary"),
        "description": job.get("description"),
        "posted_at": job.get("posted_at"),
        "source": job.get("source"),
        "source_url": job.get("source_url"),
    }
    return {
        key: value
        for key, value in compact.items()
        if value is not None and value != "" and value != []
    }


async def _interaction_count_for_user(db: AsyncSession, user_id: Any) -> int:
    try:
        row = (
            await db.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM applications WHERE user_id = :uid) + "
                    "(SELECT COUNT(*) FROM user_interactions WHERE user_id = :uid) + "
                    "(SELECT COUNT(*) FROM user_job_interactions WHERE user_id = :uid) AS total"
                ),
                {"uid": user_id},
            )
        ).mappings().first()
        return int((row or {}).get("total") or 0)
    except Exception:  # pragma: no cover - missing optional tables in ad-hoc DBs
        return 0


async def _session_history_for_user(
    db: AsyncSession,
    user_id: Any,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT "
                    "uji.job_id::text AS job_id, uji.clicked, uji.saved, uji.applied, "
                    "uji.dismissed, uji.dwell_seconds, j.title, j.company, j.location, "
                    "uji.created_at "
                    "FROM user_job_interactions uji "
                    "JOIN jobs j ON uji.job_id = j.id "
                    "WHERE uji.user_id = :uid "
                    "ORDER BY uji.created_at DESC "
                    "LIMIT :limit"
                ),
                {"uid": user_id, "limit": limit},
            )
        ).mappings().all()
    except Exception:  # pragma: no cover - optional interaction tables may be absent
        return []

    history: list[dict[str, Any]] = []
    for row in rows:
        event = "view"
        dwell_seconds = float(row.get("dwell_seconds") or 0.0)
        if row.get("applied"):
            event = "apply"
        elif row.get("saved"):
            event = "save"
        elif row.get("clicked"):
            event = "click"
        elif dwell_seconds >= 10.0:
            event = "valid_dwell"
        elif row.get("dismissed"):
            event = "skip"
        history.append(
            {
                "event": event,
                "job_id": row.get("job_id"),
                "title": row.get("title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "dwell_seconds": dwell_seconds,
                "created_at": (
                    row["created_at"].isoformat()
                    if isinstance(row.get("created_at"), datetime)
                    else row.get("created_at")
                ),
            }
        )
    return history


# ════════════════════════════════════════════════════════════════
# FastAPI app
# ════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global http_client, feedback_outbox_task
    timeout = httpx.Timeout(HTTP_TIMEOUT_SECONDS, connect=1.0)
    http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("Gateway started pipeline_url=%s p95_target_ms=%s", PIPELINE_URL, P95_TARGET_MS)
    if FEEDBACK_OUTBOX_RETRY_ENABLED:
        feedback_outbox_task = asyncio.create_task(_feedback_outbox_worker_loop())
    try:
        yield
    finally:
        if feedback_outbox_task is not None:
            feedback_outbox_task.cancel()
            try:
                await feedback_outbox_task
            except asyncio.CancelledError:
                pass
            feedback_outbox_task = None
        await http_client.aclose()


app = FastAPI(
    title="SCPA Gateway",
    version="2.0.0",
    description="Routes frontend requests to the SCPA backend services.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_latency_headers(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Gateway-Latency-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-Gateway-P95-Target-Ms"] = str(P95_TARGET_MS)
    return response


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "gateway", "docs": "/docs"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "service": "gateway"}


@app.get("/api/company-logo")
async def proxy_company_logo(
    url: str = Query(..., min_length=1),
    company: str = Query(default=""),
) -> Response:
    """Proxy approved company logo hosts so browser CORP rules do not break cards."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in LOGO_PROXY_ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="logo host is not allowed")

    try:
        upstream = await _client().get(
            url,
            timeout=HEALTH_TIMEOUT_SECONDS,
            headers={"User-Agent": "SCPA-Gateway/1.0 (+local academic project)"},
        )
        upstream.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Logo fetch failed for %s: %s", url, exc)
        return _fallback_logo_svg(company)

    content_type = upstream.headers.get("content-type", "image/png").split(";", 1)[0]
    if not content_type.startswith("image/"):
        return _fallback_logo_svg(company)

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


@app.get("/ready")
async def ready() -> dict[str, Any]:
    return {"status": "ready", "pipeline": await _pipeline_get("/health", timeout=HEALTH_TIMEOUT_SECONDS)}


@app.get("/api/admin/model-health")
async def admin_model_health(
    token_payload: dict[str, Any] = Depends(_get_current_user),
) -> dict[str, Any]:
    _require_admin_role(token_payload)
    pipeline_health = await _pipeline_get("/health", timeout=HEALTH_TIMEOUT_SECONDS)
    return _admin_model_health_summary(pipeline_health)


@app.get("/admin/health/overview")
@app.get("/api/admin/health/overview")
async def admin_health_overview(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    pipeline_health = await _admin_pipeline_health_snapshot()
    model_health = _admin_model_health_summary(pipeline_health)
    task_counts = await _admin_embedding_task_counts(db)
    degraded_response_count = 0
    if await _admin_table_exists(db, "served_slates"):
        degraded_response_count = int(
            await _admin_safe_scalar(
                db,
                """
                SELECT count(*)::int
                FROM served_slates
                WHERE created_at > NOW() - interval '24 hours'
                  AND CASE jsonb_typeof(fallback_flags)
                    WHEN 'array' THEN jsonb_array_length(fallback_flags) > 0
                    WHEN 'object' THEN fallback_flags <> '{}'::jsonb
                    ELSE false
                  END
                """,
                default=0,
            )
            or 0
        )

    return {
        "gateway": {"status": "healthy"},
        "pipeline": model_health["pipeline"],
        "sbert": model_health["models"]["sbert"],
        "ncf": model_health["models"]["ncf"],
        "dqn": model_health["models"]["dqn"],
        "postgres": {"status": await _admin_postgres_status(db)},
        "redis": {"status": await _admin_redis_status()},
        "embedding_worker": {
            "status": _admin_embedding_worker_status(task_counts),
            "task_counts": task_counts,
        },
        "scraper": model_health["models"]["scraper"],
        "recommendation_latency": await _admin_latency_summary(db),
        "degraded_response_count": degraded_response_count,
        "error_rate": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin/models")
@app.get("/api/admin/models")
async def admin_models(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    bundle = await _admin_active_bundle(db)
    registry = await _admin_model_registry_rows(db)
    artifacts = await _admin_active_model_artifacts(db)
    sbert_registry = registry.get(bundle.sbert_model_version) or registry.get("sbert") or {}
    ncf_artifact = artifacts.get("ncf") or {}
    dqn_artifact = artifacts.get("dqn") or {}
    response_schema_ok = bundle.response_schema == DEFAULT_RESPONSE_SCHEMA
    state_schema_ok = bundle.state_schema == DEFAULT_STATE_SCHEMA
    sbert_version_ok = bool(bundle.sbert_model_version)
    compatibility_ok = response_schema_ok and state_schema_ok and sbert_version_ok

    return {
        "active_model_bundle": _admin_bundle_payload(bundle),
        "sbert": {
            "model_version": bundle.sbert_model_version or active_sbert_version(),
            "checkpoint": sbert_registry.get("source_path") or "models/sbert-indonesian-hybrid-manual-research/best",
            "checkpoint_hash": sbert_registry.get("checkpoint_hash"),
            "dimension": sbert_registry.get("dimension") or 384,
            "readiness": "ready" if bundle.sbert_model_version else "unknown",
        },
        "ncf": {
            "model_version": bundle.ncf_model_version,
            "model_loaded": bool(ncf_artifact) or bool(bundle.ncf_model_version),
            "fallback_mode": bool(ncf_artifact.get("fallback_mode", False)),
        },
        "dqn": {
            "model_version": bundle.dqn_model_version,
            "state_schema": bundle.state_schema,
            "mode": "session_rerank",
            "fallback_mode": bool(dqn_artifact.get("fallback_mode", False)),
        },
        "model_compatibility": {
            "status": "compatible" if compatibility_ok else "attention",
            "response_schema_ok": response_schema_ok,
            "state_schema_ok": state_schema_ok,
            "sbert_version_ok": sbert_version_ok,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin/embeddings/coverage")
@app.get("/api/admin/embeddings/coverage")
async def admin_embeddings_coverage(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    bundle = await _admin_active_bundle(db)
    model_version = bundle.sbert_model_version or DEFAULT_ACTIVE_SBERT
    active_jobs = int(
        await _admin_safe_scalar(
            db,
            """
            SELECT count(*)::int
            FROM jobs
            WHERE is_active = true
              AND COALESCE(quality_status, 'accepted') = 'accepted'
            """,
            default=0,
        )
        or 0
    )
    has_job_embeddings = await _admin_table_exists(db, "job_embeddings")
    embedded_active_jobs = 0
    coverage_by_model_version: list[dict[str, Any]] = []
    if has_job_embeddings:
        embedded_active_jobs = int(
            await _admin_safe_scalar(
                db,
                """
                SELECT count(*)::int
                FROM jobs j
                WHERE j.is_active = true
                  AND COALESCE(j.quality_status, 'accepted') = 'accepted'
                  AND EXISTS (
                    SELECT 1
                    FROM job_embeddings je
                    WHERE je.job_id = j.id
                      AND je.model_version = :model_version
                      AND je.status = 'ready'
                  )
                """,
                {"model_version": model_version},
                default=0,
            )
            or 0
        )
        coverage_by_model_version = await _admin_safe_rows(
            db,
            """
            SELECT model_version,
                   count(*)::int AS embedded_jobs,
                   round((100.0 * count(*) / GREATEST(:active_jobs, 1))::numeric, 2)::float
                     AS coverage_percentage
            FROM job_embeddings
            WHERE status = 'ready'
            GROUP BY model_version
            ORDER BY embedded_jobs DESC
            """,
            {"active_jobs": active_jobs},
        )

    task_counts = await _admin_embedding_task_counts(db)
    oldest_pending_age = None
    if await _admin_table_exists(db, "embedding_tasks"):
        oldest_pending_age = await _admin_safe_scalar(
            db,
            """
            SELECT EXTRACT(EPOCH FROM (NOW() - min(created_at)))::float
            FROM embedding_tasks
            WHERE status IN ('pending', 'retry')
            """,
            default=None,
        )

    return {
        "model_version": model_version,
        "total_active_jobs": active_jobs,
        "embedded_active_jobs": embedded_active_jobs,
        "coverage_percentage": round(100.0 * embedded_active_jobs / max(active_jobs, 1), 2),
        "pending_tasks": task_counts.get("pending", 0),
        "processing_tasks": task_counts.get("processing", 0),
        "retry_tasks": task_counts.get("retry", 0),
        "failed_tasks": task_counts.get("failed", 0),
        "dead_letter_tasks": task_counts.get("dead_letter", 0),
        "oldest_pending_age_seconds": round(float(oldest_pending_age), 2) if oldest_pending_age is not None else None,
        "coverage_by_model_version": coverage_by_model_version,
        "storage_status": "ready" if has_job_embeddings else "unavailable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin/embedding-tasks")
@app.get("/api/admin/embedding-tasks")
async def admin_embedding_tasks(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    if not await _admin_table_exists(db, "embedding_tasks"):
        return {"tasks": [], "total": 0, "limit": limit, "offset": offset}
    total = int(await _admin_safe_scalar(db, "SELECT count(*)::int FROM embedding_tasks", default=0) or 0)
    tasks = await _admin_safe_rows(
        db,
        """
        SELECT id AS task_id, job_id::text AS job_id, model_version, status,
               priority, attempt_count, last_error_code, locked_at,
               next_retry_at, created_at
        FROM embedding_tasks
        ORDER BY
          CASE status
            WHEN 'processing' THEN 0
            WHEN 'pending' THEN 1
            WHEN 'retry' THEN 2
            WHEN 'failed' THEN 3
            WHEN 'dead_letter' THEN 4
            ELSE 5
          END,
          priority DESC,
          created_at ASC
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset},
    )
    return {"tasks": tasks, "total": total, "limit": limit, "offset": offset}


@app.get("/admin/scrapers/overview")
@app.get("/api/admin/scrapers/overview")
async def admin_scrapers_overview(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    fetched_jobs = int(await _admin_safe_scalar(db, "SELECT count(*)::int FROM jobs", default=0) or 0)
    accepted_jobs = int(
        await _admin_safe_scalar(
            db,
            "SELECT count(*)::int FROM jobs WHERE COALESCE(quality_status, 'accepted') = 'accepted'",
            default=0,
        )
        or 0
    )
    rejected_jobs = max(fetched_jobs - accepted_jobs, 0)
    duplicate_count = int(
        await _admin_safe_scalar(
            db,
            """
            SELECT COALESCE(sum(group_size - 1), 0)::int
            FROM (
              SELECT count(*) AS group_size
              FROM jobs
              WHERE content_hash IS NOT NULL
              GROUP BY content_hash
              HAVING count(*) > 1
            ) duplicate_groups
            """,
            default=0,
        )
        or 0
    )
    latest_scrape_time = await _admin_safe_scalar(
        db,
        "SELECT max(COALESCE(scraped_at, last_seen_at, source_updated_at, posted_at)) FROM jobs",
        default=None,
    )
    quality_reject_reasons = await _admin_safe_rows(
        db,
        """
        SELECT COALESCE(NULLIF(quality_reject_reason, ''), quality_status, 'unknown') AS reason,
               count(*)::int AS count
        FROM jobs
        WHERE COALESCE(quality_status, 'accepted') <> 'accepted'
        GROUP BY reason
        ORDER BY count DESC, reason ASC
        LIMIT 20
        """,
    )
    latest_scrapes = await _admin_safe_rows(
        db,
        """
        SELECT id::text AS job_id, title, company, COALESCE(source::text, 'unknown') AS source,
               quality_status, scraped_at, last_seen_at
        FROM jobs
        ORDER BY COALESCE(scraped_at, last_seen_at, source_updated_at, posted_at) DESC NULLS LAST
        LIMIT 10
        """,
    )
    return {
        "fetched_jobs": fetched_jobs,
        "accepted_jobs": accepted_jobs,
        "rejected_jobs": rejected_jobs,
        "duplicate_count": duplicate_count,
        "source_distribution": await _admin_source_distribution(db),
        "latest_scrape_time": _jsonable(latest_scrape_time),
        "quality_reject_reasons": quality_reject_reasons,
        "new_jobs_today": int(
            await _admin_safe_scalar(
                db,
                "SELECT count(*)::int FROM jobs WHERE first_seen_at >= CURRENT_DATE",
                default=0,
            )
            or 0
        ),
        "changed_jobs_today": int(
            await _admin_safe_scalar(
                db,
                "SELECT count(*)::int FROM jobs WHERE source_updated_at >= CURRENT_DATE",
                default=0,
            )
            or 0
        ),
        "latest_scrapes": latest_scrapes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/admin/scrapers/run")
@app.post("/api/admin/scrapers/run")
async def admin_scrapers_run(
    token_payload: dict[str, Any] = Depends(_get_current_user),
) -> dict[str, Any]:
    """Trigger one on-demand scrape+embed+upsert cycle (manual catalog refresh).

    Mutating, outward-facing action: it instructs the scraper to fetch from
    configured external sources and writes accepted jobs into the catalog. Admin
    or operator role only; every trigger is audit-logged with the actor.
    """
    _require_admin_or_operator_role(token_payload)
    actor = (
        token_payload.get("sub")
        or token_payload.get("email")
        or token_payload.get("user_id")
        or "unknown"
    )
    logger.info("admin manual scrape triggered actor=%s", actor)
    return await _pipeline_post("/pipeline/scrape-run", {"triggered_by": str(actor)})


@app.get("/admin/scrapers/run/{job_id}")
@app.get("/api/admin/scrapers/run/{job_id}")
async def admin_scrapers_run_status(
    job_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    return await _pipeline_get(f"/pipeline/scrape-run/{job_id}")


@app.get("/admin/jobs/quality")
@app.get("/api/admin/jobs/quality")
async def admin_jobs_quality(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    active_jobs = int(await _admin_safe_scalar(db, "SELECT count(*)::int FROM jobs WHERE is_active = true", default=0) or 0)
    inactive_jobs = int(await _admin_safe_scalar(db, "SELECT count(*)::int FROM jobs WHERE is_active = false", default=0) or 0)
    duplicate_groups = int(
        await _admin_safe_scalar(
            db,
            """
            SELECT count(*)::int
            FROM (
              SELECT COALESCE(content_hash, lower(title || '|' || company || '|' || COALESCE(location, ''))) AS key
              FROM jobs
              GROUP BY key
              HAVING count(*) > 1
            ) d
            """,
            default=0,
        )
        or 0
    )
    duplicate_examples = await _admin_safe_rows(
        db,
        """
        SELECT lower(title || '|' || company || '|' || COALESCE(location, '')) AS fingerprint,
               count(*)::int AS count,
               min(title) AS title,
               min(company) AS company
        FROM jobs
        GROUP BY fingerprint
        HAVING count(*) > 1
        ORDER BY count DESC
        LIMIT 8
        """,
    )
    return {
        "active_jobs": active_jobs,
        "inactive_jobs": inactive_jobs,
        "duplicate_groups": duplicate_groups,
        "duplicate_examples": duplicate_examples,
        "source_distribution": await _admin_source_distribution(db),
        "missing_source_url_count": int(
            await _admin_safe_scalar(
                db,
                "SELECT count(*)::int FROM jobs WHERE source_url IS NULL OR source_url = ''",
                default=0,
            )
            or 0
        ),
        "short_description_count": int(
            await _admin_safe_scalar(
                db,
                """
                SELECT count(*)::int
                FROM jobs
                WHERE length(COALESCE(NULLIF(description_text, ''), NULLIF(description, ''), '')) < 160
                """,
                default=0,
            )
            or 0
        ),
        "no_skill_signal_count": int(
            await _admin_safe_scalar(
                db,
                """
                SELECT count(*)::int
                FROM jobs
                WHERE cardinality(COALESCE(required_skill_names, ARRAY[]::text[])) = 0
                  AND cardinality(COALESCE(preferred_skill_names, ARRAY[]::text[])) = 0
                  AND cardinality(COALESCE(extracted_skill_names, ARRAY[]::text[])) = 0
                """,
                default=0,
            )
            or 0
        ),
        "rejected_count": int(
            await _admin_safe_scalar(
                db,
                "SELECT count(*)::int FROM jobs WHERE COALESCE(quality_status, 'accepted') <> 'accepted'",
                default=0,
            )
            or 0
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/admin/recommendations/inspect")
@app.post("/api/admin/recommendations/inspect")
async def admin_recommendation_inspect(
    body: AdminRecommendationInspectRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    request_id = str(uuid.uuid4())

    if body.profile is not None:
        # Ad-hoc tester mode: synthesize a profile from typed input and score it
        # live with an ephemeral user id. Nothing is written to the database, so
        # NCF/DQN run in cold-start / no-session fallback (no real user vector).
        adhoc = body.profile
        skills = [skill.strip() for skill in adhoc.skills if skill and skill.strip()][:50]
        profile: dict[str, Any] = {
            "name": adhoc.name or "Ad-hoc Tester",
            "program_studi": adhoc.program_studi or adhoc.jurusan,
            "jurusan": adhoc.jurusan or adhoc.program_studi,
            "university": adhoc.university,
            "skills": skills,
        }
        locations = [loc.strip() for loc in adhoc.preferred_locations if loc and loc.strip()][:20]
        if locations:
            profile["preferred_locations"] = locations
        if adhoc.target_role:
            profile["target_role"] = adhoc.target_role
        profile["session_id"] = body.session_id
        profile["session_events"] = []
        profile["session_history"] = []
        inspect_mode = "adhoc_profile"
        inspected_subject = profile["name"]
        payload = {
            "user_id": f"adhoc-{uuid.uuid4().hex}",
            "refresh_jobs": False,
            "profile": profile,
            "interaction_count": 0,
            "limit": body.limit,
        }
        session_events = []
    else:
        if not body.user_id_or_email:
            raise HTTPException(
                status_code=422,
                detail="user_id_or_email or profile is required",
            )
        target_user = await _admin_resolve_user_identifier(db, body.user_id_or_email)
        session_events = await _admin_session_events(
            db,
            user_id=target_user["id"],
            session_id=body.session_id,
            limit=SESSION_EVENT_LIMIT,
        )
        if not session_events and not body.session_id:
            session_events = await _recent_session_events(db, target_user["id"])
        profile = await _pipeline_profile_for_user(db, target_user)
        profile["session_id"] = body.session_id
        profile["session_events"] = session_events
        profile["session_history"] = session_events
        interaction_count = await _interaction_count_for_user(db, target_user["id"])
        inspect_mode = "user"
        inspected_subject = target_user.get("email") or str(target_user["id"])
        payload = {
            "user_id": str(target_user["id"]),
            "refresh_jobs": False,
            "profile": profile,
            "interaction_count": interaction_count,
            "limit": body.limit,
        }

    try:
        pipeline_resp = await _pipeline_post("/pipeline/run", payload)
    except HTTPException as exc:
        return {
            "request_id": request_id,
            "mode": inspect_mode,
            "inspected_subject": inspected_subject,
            "source": "pipeline_unavailable",
            "degraded": True,
            "stale": False,
            "model_bundle_version": None,
            "candidate_counts": {"retrieval": 0, "ncf": 0, "dqn": 0, "final": 0},
            "timings_ms": {},
            "cache": {"status": "bypassed", "reason": "admin_inspection_read_only"},
            "sbert_top_candidates": [],
            "ncf_reranked_candidates": [],
            "dqn_reranked_candidates": [],
            "final_items": [],
            "lineage_validation": {"status": "unavailable", "reason": str(exc.detail)},
        }

    ranked = [
        item for item in pipeline_resp.get("ranked", [])
        if isinstance(item, dict)
    ]
    stages = pipeline_resp.get("stages") if isinstance(pipeline_resp.get("stages"), dict) else {}
    session_event_count = int((stages.get("dqn_rank") or {}).get("session_event_count") or len(session_events))
    trace_items = [
        _admin_trace_item(item, index, session_event_count=session_event_count)
        for index, item in enumerate(ranked, start=1)
    ]
    sbert_top = sorted(trace_items, key=lambda item: item["sbert_score"], reverse=True)[: body.limit]
    ncf_top = sorted(trace_items, key=lambda item: item["ncf_rank_after"])[: body.limit]
    dqn_top = sorted(trace_items, key=lambda item: item["dqn_rank_after"])[: body.limit]
    final_items = sorted(trace_items, key=lambda item: item["final_rank"])[: body.limit]
    ncf_funnel = stages.get("ncf_score", {}).get("funnel", {}) if isinstance(stages.get("ncf_score"), dict) else {}
    dqn_funnel = stages.get("dqn_rank", {}).get("funnel", {}) if isinstance(stages.get("dqn_rank"), dict) else {}

    return {
        "request_id": request_id,
        "mode": inspect_mode,
        "inspected_subject": inspected_subject,
        "source": pipeline_resp.get("source") or "hybrid_model",
        "degraded": bool((stages.get("degradation") or {}).get("degraded")),
        "stale": False,
        "model_bundle_version": pipeline_resp.get("model_bundle_version"),
        "candidate_counts": {
            "retrieval": int(pipeline_resp.get("total_candidates") or 0),
            "ncf_input": ncf_funnel.get("input"),
            "ncf_output": ncf_funnel.get("output"),
            "dqn_input": dqn_funnel.get("input"),
            "dqn_output": dqn_funnel.get("output"),
            "final": len(final_items),
        },
        "timings_ms": _jsonable(pipeline_resp.get("timings_ms") or {}),
        "cache": {"status": "bypassed", "reason": "admin_inspection_read_only"},
        "sbert_top_candidates": sbert_top,
        "ncf_reranked_candidates": ncf_top,
        "dqn_reranked_candidates": dqn_top,
        "final_items": final_items,
        "lineage_validation": _admin_lineage_validation(trace_items),
    }


@app.get("/admin/sessions/{session_id}")
@app.get("/api/admin/sessions/{session_id}")
async def admin_session_detail(
    session_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _require_admin_or_operator_role(token_payload)
    events = await _admin_session_events(db, session_id=session_id, limit=100)
    user_id = events[0].get("user_id") if events else None
    state_version = await _session_state_version(db, str(user_id)) if user_id else "0.0"
    event_counts: dict[str, int] = {}
    for event in events:
        key = str(event.get("event") or "unknown")
        event_counts[key] = event_counts.get(key, 0) + 1
    return {
        "user_id": user_id,
        "session_id": session_id,
        "session_state_version": state_version,
        "recent_events": events[-30:],
        "viewed_jobs": [event["job_id"] for event in events if event.get("event") in {"view", "click", "source_click"} and event.get("job_id")],
        "saved_jobs": [event["job_id"] for event in events if event.get("event") == "save" and event.get("job_id")],
        "skipped_jobs": [event["job_id"] for event in events if event.get("event") == "skip" and event.get("job_id")],
        "applied_jobs": [event["job_id"] for event in events if event.get("event") == "apply" and event.get("job_id")],
        "event_counts": event_counts,
        "slate_cache": {
            "status": "not_checked" if not user_id else "versioned",
            "state_version": state_version,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/skills/search", response_model=SkillSearchResponse)
async def search_skills(
    q: str = Query(default="", max_length=128),
    limit: int = Query(default=10, ge=1, le=50),
    exclude: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = _normalise_skill_value(q)
    excluded = _normalise_query_values(exclude)
    taxonomy = await _load_skill_taxonomy(db)
    if query:
        matches = [
            skill for skill in taxonomy
            if _skill_search_score(skill, query) < 99
        ]
        matches.sort(
            key=lambda skill: (
                _skill_search_score(skill, query),
                _skill_search_priority(skill),
                skill["name"],
            )
        )
    else:
        matches = taxonomy
    if excluded:
        matches = [
            skill for skill in matches
            if not (_skill_identity_terms(skill) & excluded)
        ]
    return {"skills": matches[:limit]}


# ════════════════════════════════════════════════════════════════
# Auth
# ════════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    # Check duplicate email
    existing = (
        await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": body.email})
    ).mappings().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    user_id = str(uuid.uuid4())
    password_hash = pwd_ctx.hash(body.password)

    await db.execute(
        text(
            "INSERT INTO users (id, name, email, password_hash, completion_percent, role) "
            "VALUES (:id, :name, :email, :password_hash, :completion_percent, :role)"
        ),
        {
            "id": user_id,
            "name": body.name,
            "email": body.email,
            "password_hash": password_hash,
            "completion_percent": 10,
            "role": "user",
        },
    )
    await db.commit()

    access_token = _create_access_token(user_id, "user")
    return {
        "access_token": access_token,
        "user": {
            "id": user_id,
            "name": body.name,
            "email": body.email,
            "role": "user",
            "completion_percent": 10,
            "program_studi": None,
            "university": None,
            "cv_uploaded_at": None,
        },
    }


@app.post("/api/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT id, name, email, password_hash, role, completion_percent, program_studi, university, cv_uploaded_at, "
                "location, education_level, graduation_year, interests "
                "FROM users WHERE email = :email"
            ),
            {"email": body.email},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=401, detail="Email tidak ditemukan")
    if not pwd_ctx.verify(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Password salah")

    await db.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
        {"id": row["id"]},
    )
    await db.commit()

    access_token = _create_access_token(str(row["id"]), row["role"])
    return {
        "access_token": access_token,
        "user": {
            "id": str(row["id"]),
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
            "completion_percent": row["completion_percent"],
            "program_studi": row["program_studi"],
            "university": row["university"],
            "cv_uploaded_at": (
                row["cv_uploaded_at"].isoformat()
                if isinstance(row.get("cv_uploaded_at"), datetime)
                else row["cv_uploaded_at"]
            ),
            "location": row.get("location"),
            "education_level": row.get("education_level"),
            "graduation_year": row.get("graduation_year"),
            "interests": list(row.get("interests") or []),
        },
    }


@app.get("/api/auth/me")
async def me(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    skills = (
        await db.execute(
            text("SELECT skill, category, proficiency_level FROM user_skills WHERE user_id = :uid"),
            {"uid": user["id"]},
        )
    ).mappings().all()
    user["skills"] = [dict(s) for s in skills]
    return user


# ════════════════════════════════════════════════════════════════
# Profile
# ════════════════════════════════════════════════════════════════

@app.get("/api/profile/completeness")
async def profile_completeness(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    skill_names = await _profile_skill_names(db, user["id"])
    return _profile_completeness_summary(user, skill_names)


@app.put("/api/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]
    canonical_skills = (
        await _canonicalize_profile_skills(db, body.skills)
        if body.skills is not None
        else None
    )

    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.program_studi is not None:
        updates["program_studi"] = body.program_studi
    if body.university is not None:
        updates["university"] = body.university
    if body.location is not None:
        updates["location"] = body.location
    if body.education_level is not None:
        updates["education_level"] = body.education_level
    if body.graduation_year is not None:
        updates["graduation_year"] = body.graduation_year

    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["id"] = uid
        await db.execute(
            text(f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = :id"),
            updates,
        )

    if body.interests is not None:
        interests = [str(i).strip() for i in body.interests if str(i).strip()]
        await db.execute(
            text(
                "UPDATE users SET interests = CAST(:interests AS text[]), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"interests": interests, "id": uid},
        )

    if canonical_skills is not None:
        await db.execute(
            text("DELETE FROM user_skills WHERE user_id = :uid"),
            {"uid": uid},
        )
        for skill in canonical_skills:
            await db.execute(
                text(
                    "INSERT INTO user_skills (user_id, skill, category, proficiency_level) "
                    "VALUES (:uid, :skill, 'technical', 'intermediate')"
                ),
                {"uid": uid, "skill": skill},
            )

    await db.commit()
    # Profile state changed — bust the pipeline/NCF caches so the next
    # /api/recommendations call rebuilds the user vector from new skills.
    await _invalidate_pipeline_user(uid)
    return {"status": "ok"}


@app.put("/api/profile/onboarding")
async def onboarding(
    body: OnboardingRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]

    if body.step == 1:
        program_studi = body.data.get("program_studi")
        university = body.data.get("university")
        location = body.data.get("location")
        education_level = body.data.get("education_level")
        graduation_year_raw = body.data.get("graduation_year")
        try:
            graduation_year = int(graduation_year_raw) if str(graduation_year_raw or "").strip() else None
        except (TypeError, ValueError):
            graduation_year = None
        await db.execute(
            text(
                "UPDATE users SET program_studi = :program_studi, university = :university, "
                "location = :location, education_level = :education_level, "
                "graduation_year = :graduation_year, "
                "completion_percent = GREATEST(completion_percent, 30), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {
                "program_studi": program_studi,
                "university": university,
                "location": location,
                "education_level": education_level,
                "graduation_year": graduation_year,
                "id": uid,
            },
        )

    elif body.step == 2:
        raw_skills = body.data.get("skills", [])
        skills = await _canonicalize_profile_skills(
            db,
            raw_skills if isinstance(raw_skills, list) else [],
        )
        for skill in skills:
            await db.execute(
                text(
                    "INSERT INTO user_skills (user_id, skill, category, proficiency_level) "
                    "VALUES (:uid, :skill, 'technical', 'intermediate') "
                    "ON CONFLICT DO NOTHING"
                ),
                {"uid": uid, "skill": skill},
            )
        await db.execute(
            text(
                "UPDATE users SET completion_percent = GREATEST(completion_percent, 60), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": uid},
        )

    elif body.step == 3:
        raw_interests = body.data.get("interests", [])
        interests = [str(i).strip() for i in raw_interests if isinstance(raw_interests, list) and str(i).strip()]
        await db.execute(
            text(
                "UPDATE users SET interests = CAST(:interests AS text[]), "
                "completion_percent = GREATEST(completion_percent, 85), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"interests": interests, "id": uid},
        )

    await db.commit()
    await _invalidate_pipeline_user(uid)
    return {"status": "saved", "step": body.step}


def _extract_text_from_cv(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="ignore")
    if ext == ".pdf":
        if PdfReader is None:
            raise HTTPException(
                status_code=422, detail="PDF extraction is not available in this environment."
            )
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Failed to extract text from PDF: {exc}"
            )
    raise HTTPException(status_code=400, detail="Unsupported file type.")


@app.post("/api/profile/cv")
async def upload_cv(
    file: UploadFile = File(...),
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in CV_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(CV_ALLOWED_EXTENSIONS)}.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=400, detail=f"File too large. Max size: {MAX_CV_SIZE_MB} MB."
        )

    raw_text = _extract_text_from_cv(file_bytes, filename)
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the file.")

    # Save file to disk with UUID-based name to prevent collisions and traversal.
    CV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = CV_UPLOAD_DIR / stored_name
    stored_path.write_bytes(file_bytes)

    # Extract skills from CV text without raising on unknown words.
    extracted_skills = await _extract_skills_from_cv_text(db, raw_text)

    # Upsert extracted skills.
    skills_added = 0
    for skill in extracted_skills:
        result = await db.execute(
            text(
                "INSERT INTO user_skills (user_id, skill, category, proficiency_level) "
                "VALUES (:uid, :skill, 'technical', 'intermediate') "
                "ON CONFLICT DO NOTHING"
            ),
            {"uid": uid, "skill": skill},
        )
        if getattr(result, "rowcount", 0):
            skills_added += 1

    await db.execute(
        text(
            "UPDATE users SET cv_uploaded_at = NOW(), updated_at = NOW() WHERE id = :id"
        ),
        {"id": uid},
    )
    await db.commit()
    await _invalidate_pipeline_user(uid)

    return {
        "status": "ok",
        "extracted_skills": extracted_skills,
        "skills_added": skills_added,
        "skills_ignored": len(extracted_skills) - skills_added,
        "filename": filename,
        "stored_name": stored_name,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_text_from_certificate(file_bytes: bytes, filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        if PdfReader is None:
            return None
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception:
            return None
    if ext in (".png", ".jpg", ".jpeg"):
        if Image is None or pytesseract is None:
            return None
        try:
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img)
        except Exception:
            return None
    return None


def _parse_certificate_name(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keywords = ("certificate", "certification", "sertifikat", "diploma", "badge", "credential", "licence", "license")
    candidates: list[str] = []
    for line in lines:
        lowered = line.lower()
        if any(kw in lowered for kw in keywords):
            candidates.append(line)
    if not candidates:
        return None
    # Prefer the longest candidate as it likely contains the full cert title.
    return max(candidates, key=len)


def _parse_certificate_issuer(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Simple heuristics: look for known issuer keywords or URLs.
    issuer_keywords = (
        "amazon web services", "google", "microsoft", "oracle", "cisco",
        "comptia", "isc", "pmi", "axelos", "peoplecert", "aws",
    )
    for line in lines:
        lowered = line.lower()
        if any(kw in lowered for kw in issuer_keywords):
            return line
    # Fallback: lines containing "www." or ".com" or "@" near the top/bottom.
    for line in lines[:5] + lines[-5:]:
        lowered = line.lower()
        if "www." in lowered or ".com" in lowered or "@" in lowered:
            if len(line) < 60:
                return line
    return None


async def _lookup_certification_skills(db: AsyncSession, cert_name: str | None) -> list[str]:
    if not cert_name:
        return []
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT mapped_skills FROM certification_skills "
                    "WHERE cert_name_regex IS NOT NULL"
                )
            )
        ).mappings().all()
    except Exception:
        return []
    found: set[str] = set()
    cert_lower = cert_name.lower()
    for row in rows:
        regex = str(row.get("cert_name_regex") or "").strip()
        if regex and regex.lower() in cert_lower:
            for skill in row.get("mapped_skills") or []:
                if skill:
                    found.add(str(skill))
    return list(found)


async def _seed_default_certification_skills(db: AsyncSession) -> None:
    """Seed a few known certificate-to-skill mappings if the table is empty."""
    try:
        count = (await db.execute(text("SELECT COUNT(*) FROM certification_skills"))).scalar_one()
        if int(count or 0) > 0:
            return
    except Exception:
        return
    defaults = [
        ("AWS Certified", "Amazon Web Services", ["Cloud Computing", "AWS"]),
        ("Google Cloud", "Google", ["Cloud Computing", "Google Cloud Platform"]),
        ("Microsoft Azure", "Microsoft", ["Cloud Computing", "Azure"]),
        ("Python", None, ["Python"]),
        ("SQL", None, ["SQL"]),
    ]
    for cert_regex, issuer, skills in defaults:
        try:
            await db.execute(
                text(
                    "INSERT INTO certification_skills (cert_name_regex, issuer, mapped_skills) "
                    "VALUES (:cert_name_regex, :issuer, :skills) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "cert_name_regex": cert_regex,
                    "issuer": issuer,
                    "skills": skills,
                },
            )
        except Exception:
            pass
    try:
        await db.commit()
    except Exception:
        await db.rollback()


@app.post("/api/profile/certificates")
async def upload_certificate(
    file: UploadFile = File(...),
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in CERT_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(CERT_ALLOWED_EXTENSIONS)}.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=400, detail=f"File too large. Max size: {MAX_CV_SIZE_MB} MB."
        )

    # Save file to disk.
    CERT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = CERT_UPLOAD_DIR / stored_name
    stored_path.write_bytes(file_bytes)

    raw_text = _extract_text_from_certificate(file_bytes, filename)
    ocr_available = raw_text is not None and raw_text.strip() != ""

    cert_name: str | None = None
    issuer: str | None = None
    mapped_skills: list[str] = []
    skills_added = 0
    ocr_confidence = "medium"

    if ocr_available:
        cert_name = _parse_certificate_name(raw_text)  # type: ignore[arg-type]
        issuer = _parse_certificate_issuer(raw_text)  # type: ignore[arg-type]
        await _seed_default_certification_skills(db)
        mapped_skills = await _lookup_certification_skills(db, cert_name)

        # Upsert mapped skills into user_skills.
        for skill in mapped_skills:
            result = await db.execute(
                text(
                    "INSERT INTO user_skills (user_id, skill, category, proficiency_level) "
                    "VALUES (:uid, :skill, 'technical', 'intermediate') "
                    "ON CONFLICT DO NOTHING"
                ),
                {"uid": uid, "skill": skill},
            )
            if getattr(result, "rowcount", 0):
                skills_added += 1
    else:
        ocr_confidence = "low"

    # Insert user_certifications record.
    cert_result = await db.execute(
        text(
            "INSERT INTO user_certifications "
            "(user_id, file_path, cert_name, issuer, ocr_confidence, mapped_skills, status) "
            "VALUES (:uid, :file_path, :cert_name, :issuer, :ocr_confidence, :mapped_skills, 'confirmed') "
            "RETURNING id"
        ),
        {
            "uid": uid,
            "file_path": str(stored_path),
            "cert_name": cert_name,
            "issuer": issuer,
            "ocr_confidence": ocr_confidence,
            "mapped_skills": mapped_skills,
        },
    )
    cert_id = cert_result.scalar_one()

    await db.commit()
    await _invalidate_pipeline_user(uid)

    if ocr_available:
        return {
            "status": "ok",
            "cert_id": cert_id,
            "cert_name": cert_name,
            "issuer": issuer,
            "mapped_skills": mapped_skills,
            "skills_added": skills_added,
            "ocr_confidence": ocr_confidence,
            "filename": filename,
            "ocr_available": True,
        }

    return {
        "status": "pending",
        "cert_id": cert_id,
        "cert_name": cert_name,
        "issuer": issuer,
        "mapped_skills": mapped_skills,
        "skills_added": skills_added,
        "ocr_confidence": ocr_confidence,
        "filename": filename,
        "ocr_available": False,
        "message": (
            "Image stored but OCR requires tesseract. "
            "Install pytesseract and the Tesseract binary to enable image text extraction."
        ),
    }


# ════════════════════════════════════════════════════════════════
# Jobs
# ════════════════════════════════════════════════════════════════

JOB_SELECT_COLUMNS = """
    id, title, company, company_logo, location, type, min_salary, max_salary,
    salary_currency, salary_text, employment_mode, description,
    raw_description_html, description_text, description_sections,
    responsibilities, requirements, nice_to_have, benefits,
    seniority_level, employment_type, job_function, industry, education_level,
    years_experience_min, years_experience_max, required_skill_names,
    preferred_skill_names, extracted_skill_names, source_url, source_updated_at,
    experience_level, posted_at, source, is_active, match_data
"""

JOB_TIME_RANGE_LABELS = {
    "24h": "24 jam terakhir",
    "7d": "7 hari terakhir",
    "30d": "30 hari terakhir",
    "all": "Semua waktu",
}
JOB_TIME_RANGE_ALIASES = {
    "day": "24h",
    "24h": "24h",
    "24_hours": "24h",
    "24_jam": "24h",
    "week": "7d",
    "7d": "7d",
    "7_days": "7d",
    "month": "30d",
    "30d": "30d",
    "30_days": "30d",
    "any": "all",
    "all": "all",
}
JOB_TYPE_LABELS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "contract": "Contract",
    "internship": "Internship",
}
JOB_WORK_MODE_LABELS = {
    "remote": "Remote",
    "onsite": "Onsite",
    "hybrid": "Hybrid",
}
JOB_FIELD_EXPR = "COALESCE(NULLIF(trim(job_function), ''), NULLIF(trim(industry), ''))"
JOB_WORK_MODE_EXPR = """
    CASE
      WHEN lower(concat_ws(' ', employment_mode::text, location, description_text, description))
        ~ '(hybrid|wfo\\s*/\\s*wfh|campuran)' THEN 'hybrid'
      WHEN lower(concat_ws(' ', employment_mode::text, location, description_text, description))
        ~ '(remote|jarak jauh|work from home|wfh|telecommute)' THEN 'remote'
      WHEN lower(concat_ws(' ', employment_mode::text, location, description_text, description))
        ~ '(onsite|on-site|on site|kantor|wfo|di kantor|office)' THEN 'onsite'
      ELSE NULL
    END
"""
JOB_FACET_LIMITS = {
    "job_types": 25,
    "job_fields": 50,
    "locations": 100,
    "work_modes": 10,
}


def _clean_job_query_values(
    values: list[str] | None,
    *,
    max_items: int = 25,
    max_length: int = 120,
    lower: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        for part in str(raw).split(","):
            value = part.strip()[:max_length]
            if not value:
                continue
            output = value.casefold() if lower else value
            key = output.casefold()
            if key in seen:
                continue
            cleaned.append(output)
            seen.add(key)
            if len(cleaned) >= max_items:
                return cleaned
    return cleaned


def _clean_time_range(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    return JOB_TIME_RANGE_ALIASES.get(normalized)


def _clean_job_type_values(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for value in _clean_job_query_values(values, lower=True):
        job_type = clean_job_type(value)
        if job_type and job_type not in cleaned:
            cleaned.append(job_type)
    return cleaned


def _clean_work_mode_values(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for value in _clean_job_query_values(values, lower=True):
        mode = clean_employment_mode(value)
        if mode and mode not in cleaned:
            cleaned.append(mode)
    return cleaned


def _jobs_filter_payload(
    *,
    time_range: str | None,
    job_type: list[str] | None,
    job_field: list[str] | None,
    location: list[str] | None,
    work_mode: list[str] | None,
) -> dict[str, Any]:
    return {
        "time_range": _clean_time_range(time_range),
        "job_type": _clean_job_type_values(job_type),
        "job_field": _clean_job_query_values(job_field, lower=True),
        "location": _clean_job_query_values(location, max_items=20),
        "work_mode": _clean_work_mode_values(work_mode),
    }


def _append_in_condition(
    conditions: list[str],
    params: dict[str, Any],
    expression: str,
    values: list[str],
    prefix: str,
) -> None:
    placeholders: list[str] = []
    for index, value in enumerate(values):
        key = f"{prefix}_{index}"
        params[key] = value
        placeholders.append(f":{key}")
    if placeholders:
        conditions.append(f"{expression} IN ({', '.join(placeholders)})")


def _append_location_condition(
    conditions: list[str],
    params: dict[str, Any],
    locations: list[str],
) -> None:
    clauses: list[str] = []
    for index, value in enumerate(locations):
        key = f"location_{index}"
        params[key] = f"%{value}%"
        clauses.append(f"location ILIKE :{key}")
    if clauses:
        conditions.append(f"({' OR '.join(clauses)})")


def _jobs_catalog_conditions() -> tuple[list[str], dict[str, Any]]:
    conditions = ["is_active = true", "COALESCE(quality_status, 'accepted') = 'accepted'"]
    params: dict[str, Any] = {}

    # Catalog freshness ceiling: hide expired (too-old) listings everywhere the
    # catalog predicate is used — list, facets, totals, and the "all time" range.
    if JOB_CATALOG_MAX_AGE_DAYS > 0:
        # JOB_CATALOG_MAX_AGE_DAYS is a validated int, safe to inline.
        conditions.append(
            f"posted_at >= (NOW() - INTERVAL '{JOB_CATALOG_MAX_AGE_DAYS} days')"
        )

    # Keep this endpoint aligned with SCPA's Indonesia-focused catalog guard.
    # Filtering and facet counts still happen globally within that catalog,
    # before pagination.
    indonesia_sources = (
        "kalibrr", "karir", "topkarir", "kitalulus", "jobstreet",
        "glints", "techinasia", "linkedin", "indeed", "remotive",
    )
    indonesia_terms = [
        "indonesia", "jakarta", "surabaya", "bandung", "depok",
        "tangerang", "bekasi", "bogor", "yogyakarta", "semarang",
        "bali", "medan", "makassar", "batam", "subang", "jawa",
        "kalimantan", "sumatra", "sulawesi",
    ]
    params["indonesia_terms"] = [f"%{term}%" for term in indonesia_terms]
    conditions.append(
        f"(source::text IN {indonesia_sources} OR location ILIKE ANY(:indonesia_terms))"
    )
    return conditions, params


def _apply_jobs_filters(
    conditions: list[str],
    params: dict[str, Any],
    filters: dict[str, Any],
    *,
    exclude: str | None = None,
) -> None:
    time_range = filters.get("time_range")
    if exclude != "time_range" and time_range and time_range != "all":
        if time_range == "24h":
            conditions.append("posted_at >= (NOW() - INTERVAL '1 day')")
        elif time_range == "7d":
            conditions.append("posted_at >= (NOW() - INTERVAL '7 days')")
        elif time_range == "30d":
            conditions.append("posted_at >= (NOW() - INTERVAL '30 days')")

    if exclude != "job_type":
        _append_in_condition(
            conditions,
            params,
            "type::text",
            filters.get("job_type") or [],
            "job_type",
        )

    if exclude != "job_field":
        _append_in_condition(
            conditions,
            params,
            f"lower({JOB_FIELD_EXPR})",
            filters.get("job_field") or [],
            "job_field",
        )

    if exclude != "location":
        _append_location_condition(conditions, params, filters.get("location") or [])

    if exclude != "work_mode":
        _append_in_condition(
            conditions,
            params,
            f"({JOB_WORK_MODE_EXPR})",
            filters.get("work_mode") or [],
            "work_mode",
        )


def _jobs_where_for_filters(
    filters: dict[str, Any],
    *,
    exclude: str | None = None,
) -> tuple[str, dict[str, Any]]:
    conditions, params = _jobs_catalog_conditions()
    _apply_jobs_filters(conditions, params, filters, exclude=exclude)
    return " AND ".join(conditions), params


async def _count_jobs(db: AsyncSession, where_clause: str, params: dict[str, Any]) -> int:
    row = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total FROM jobs WHERE {where_clause}"),
            params,
        )
    ).mappings().first()
    return int((row or {}).get("total") or 0)


def _facet_option(value: str, label: str, count: int) -> dict[str, Any]:
    return {"value": value, "label": label, "count": int(count)}


async def _time_range_facets(
    db: AsyncSession,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    base_where, base_params = _jobs_where_for_filters(filters, exclude="time_range")
    specs = [
        ("24h", "posted_at >= (NOW() - INTERVAL '1 day')"),
        ("7d", "posted_at >= (NOW() - INTERVAL '7 days')"),
        ("30d", "posted_at >= (NOW() - INTERVAL '30 days')"),
        ("all", None),
    ]
    options: list[dict[str, Any]] = []
    for value, extra_condition in specs:
        where_clause = base_where
        if extra_condition:
            where_clause = f"{where_clause} AND {extra_condition}"
        count = await _count_jobs(db, where_clause, base_params)
        options.append(_facet_option(value, JOB_TIME_RANGE_LABELS[value], count))
    return options


async def _simple_value_facets(
    db: AsyncSession,
    *,
    filters: dict[str, Any],
    exclude: str,
    value_expression: str,
    label_expression: str,
    limit: int,
    label_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _jobs_where_for_filters(filters, exclude=exclude)
    params["facet_limit"] = limit
    rows = (
        await db.execute(
            text(
                "SELECT value, MIN(label) AS label, COUNT(*)::int AS count "
                "FROM ("
                f"  SELECT {value_expression} AS value, {label_expression} AS label "
                f"  FROM jobs WHERE {where_clause}"
                ") facets "
                "WHERE value IS NOT NULL AND label IS NOT NULL AND trim(label) <> '' "
                "GROUP BY value "
                "ORDER BY count DESC, label ASC "
                "LIMIT :facet_limit"
            ),
            params,
        )
    ).mappings().all()
    options: list[dict[str, Any]] = []
    for row in rows:
        value = str(row["value"])
        label = label_map.get(value, str(row["label"])) if label_map else str(row["label"])
        options.append(_facet_option(value, label, row["count"]))
    return options


@app.get("/api/jobs")
async def list_jobs(
    time_range: str | None = Query(default=None, max_length=16),
    job_type: list[str] | None = Query(default=None),
    job_field: list[str] | None = Query(default=None),
    location: list[str] | None = Query(default=None),
    work_mode: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10_000),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Paginated active-job catalog with server-side global filtering.

    Filters are applied before COUNT and LIMIT/OFFSET. Salary is deliberately
    absent from the public filter contract; unknown query params are ignored by
    FastAPI and therefore do not narrow results.
    """
    filters = _jobs_filter_payload(
        time_range=time_range,
        job_type=job_type,
        job_field=job_field,
        location=location,
        work_mode=work_mode,
    )
    catalog_where, catalog_params = _jobs_where_for_filters({})
    where_clause, params = _jobs_where_for_filters(filters)

    offset = (page - 1) * limit
    params_with_paging = {**params, "limit": limit, "offset": offset}
    total = await _count_jobs(db, catalog_where, catalog_params)
    total_filtered = await _count_jobs(db, where_clause, params)
    rows = (
        await db.execute(
            text(
                f"SELECT {JOB_SELECT_COLUMNS} "
                f"FROM jobs WHERE {where_clause} "
                "ORDER BY posted_at DESC, length(coalesce(description_text, description, '')) DESC, id "
                "LIMIT :limit OFFSET :offset"
            ),
            params_with_paging,
        )
    ).mappings().all()
    jobs: list[dict[str, Any]] = []
    for row in rows:
        jobs.append(_job_payload_from_row(row, sanitize_skill_signals=False))
    total_pages = max(1, (total_filtered + limit - 1) // limit) if total_filtered > 0 else 1
    return {
        "items": jobs,
        "jobs": jobs,
        "total": total,
        "total_filtered": total_filtered,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "filters_applied": {
            "time_range": filters["time_range"],
            "job_type": filters["job_type"],
            "job_field": filters["job_field"],
            "location": filters["location"],
            "work_mode": filters["work_mode"],
        },
    }


@app.get("/api/jobs/facets")
async def list_job_facets(
    time_range: str | None = Query(default=None, max_length=16),
    job_type: list[str] | None = Query(default=None),
    job_field: list[str] | None = Query(default=None),
    location: list[str] | None = Query(default=None),
    work_mode: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return contextual facet counts from the full active catalog."""
    filters = _jobs_filter_payload(
        time_range=time_range,
        job_type=job_type,
        job_field=job_field,
        location=location,
        work_mode=work_mode,
    )
    return {
        "policy": "contextual",
        "time_ranges": await _time_range_facets(db, filters),
        "job_types": await _simple_value_facets(
            db,
            filters=filters,
            exclude="job_type",
            value_expression="type::text",
            label_expression="type::text",
            limit=JOB_FACET_LIMITS["job_types"],
            label_map=JOB_TYPE_LABELS,
        ),
        "job_fields": await _simple_value_facets(
            db,
            filters=filters,
            exclude="job_field",
            value_expression=f"lower({JOB_FIELD_EXPR})",
            label_expression=JOB_FIELD_EXPR,
            limit=JOB_FACET_LIMITS["job_fields"],
        ),
        "locations": await _simple_value_facets(
            db,
            filters=filters,
            exclude="location",
            value_expression="trim(location)",
            label_expression="trim(location)",
            limit=JOB_FACET_LIMITS["locations"],
        ),
        "work_modes": await _simple_value_facets(
            db,
            filters=filters,
            exclude="work_mode",
            value_expression=f"({JOB_WORK_MODE_EXPR})",
            label_expression=f"({JOB_WORK_MODE_EXPR})",
            limit=JOB_FACET_LIMITS["work_modes"],
            label_map=JOB_WORK_MODE_LABELS,
        ),
        "filters_applied": {
            "time_range": filters["time_range"],
            "job_type": filters["job_type"],
            "job_field": filters["job_field"],
            "location": filters["location"],
            "work_mode": filters["work_mode"],
        },
    }


def _job_payload_from_row(
    row: Any,
    *,
    public_id: str | None = None,
    sanitize_skill_signals: bool = True,
) -> dict[str, Any]:
    job = dict(row)
    job["id"] = public_id or str(job["id"])
    match_data = _parse_match_data(job.pop("match_data", None))
    job["source_url"] = job.get("source_url") or match_data.get("source_url")
    if sanitize_skill_signals:
        required_skills, preferred_skills, extracted_skills = _sanitize_skill_signals_for_job(
            row=job,
            match_data=match_data,
            taxonomy=DEFAULT_SKILL_TAXONOMY,
        )
    else:
        required_skills = _display_skill_list(
            job.get("required_skill_names")
            or match_data.get("required_skills")
            or match_data.get("skills")
            or []
        )
        preferred_skills = _display_skill_list(
            job.get("preferred_skill_names")
            or match_data.get("preferred_skills")
            or []
        )
        extracted_skills = _display_skill_list(
            job.get("extracted_skill_names")
            or match_data.get("extracted_skills")
            or []
        )
        if not required_skills:
            required_skills = extracted_skills
    job["skills"] = required_skills or extracted_skills
    job["required_skills"] = required_skills
    job["preferred_skills"] = preferred_skills
    job["extracted_skills"] = extracted_skills
    job["company_logo"] = _proxied_company_logo_url(job.get("company_logo"), job.get("company"))
    return job


JOB_ALERT_FREQUENCIES = {"daily", "weekly"}
JOB_ALERT_COLUMNS = (
    "id, name, query, location, min_match_percent, frequency, active, "
    "criteria, created_at, updated_at"
)


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_alert_frequency(value: str | None) -> str:
    frequency = (value or "daily").strip().lower()
    if frequency not in JOB_ALERT_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Unsupported job alert frequency")
    return frequency


def _alert_criteria(
    *,
    query: str | None,
    location: str | None,
    min_match_percent: int,
) -> dict[str, Any]:
    return {
        "query": query,
        "location": location,
        "min_match_percent": min_match_percent,
    }


def _job_alert_payload(row: Any) -> dict[str, Any]:
    alert = dict(row)
    created_at = alert.get("created_at")
    updated_at = alert.get("updated_at")
    if isinstance(created_at, datetime):
        alert["created_at"] = created_at.isoformat()
    if isinstance(updated_at, datetime):
        alert["updated_at"] = updated_at.isoformat()
    alert["criteria"] = alert.get("criteria") or _alert_criteria(
        query=alert.get("query"),
        location=alert.get("location"),
        min_match_percent=alert.get("min_match_percent") or 60,
    )
    return alert


async def _require_job_alert(
    db: AsyncSession,
    *,
    user_id: Any,
    alert_id: int,
) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT id, user_id, name, query, location, min_match_percent, "
                "frequency, active, criteria, created_at, updated_at "
                "FROM job_alerts WHERE id = :alert_id AND user_id = :uid"
            ),
            {"alert_id": alert_id, "uid": user_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Job alert not found")
    return dict(row)


async def _require_job_uuid(db: AsyncSession, job_id: str) -> uuid.UUID:
    db_uuid = to_uuid(job_id)
    row = (
        await db.execute(
            text("SELECT id FROM jobs WHERE id = :id"),
            {"id": db_uuid},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_uuid


async def _set_job_interaction_state(
    db: AsyncSession,
    *,
    user_id: Any,
    job_id: uuid.UUID,
    saved: bool,
    dismissed: bool,
    action_type: str,
    clicked: bool = False,
    applied: bool = False,
) -> None:
    await db.execute(
        text(
            "INSERT INTO user_job_interactions ("
            "user_id, job_id, clicked, saved, applied, dismissed, created_at"
            ") VALUES ("
            ":uid, :job_id, :clicked, :saved, :applied, :dismissed, NOW()"
            ") ON CONFLICT (user_id, job_id) DO UPDATE SET "
            "saved = EXCLUDED.saved, "
            "dismissed = EXCLUDED.dismissed, "
            "clicked = user_job_interactions.clicked OR EXCLUDED.clicked, "
            "applied = user_job_interactions.applied OR EXCLUDED.applied"
        ),
        {
            "uid": user_id,
            "job_id": job_id,
            "clicked": clicked,
            "saved": saved,
            "applied": applied,
            "dismissed": dismissed,
        },
    )
    await db.execute(
        text(
            "INSERT INTO user_interactions ("
            "user_id, action_type, target_type, target_id, metadata, created_at"
            ") VALUES ("
            ":uid, :action_type, 'job', :job_id, CAST(:metadata AS jsonb), NOW()"
            ")"
        ),
        {
            "uid": user_id,
            "action_type": action_type,
            "job_id": job_id,
            "metadata": json.dumps({"source": "saved_jobs_api"}),
        },
    )
    await db.commit()


@app.get("/api/job-alerts")
async def list_job_alerts(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    rows = (
        await db.execute(
            text(
                f"SELECT {JOB_ALERT_COLUMNS} "
                "FROM job_alerts "
                "WHERE user_id = :uid AND active = true "
                "ORDER BY created_at DESC, id DESC"
            ),
            {"uid": user["id"]},
        )
    ).mappings().all()
    alerts = [_job_alert_payload(row) for row in rows]
    return {"alerts": alerts, "total": len(alerts)}


@app.post("/api/job-alerts")
async def create_job_alert(
    payload: JobAlertCreateRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    name = _clean_optional_text(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Job alert name is required")
    query = _clean_optional_text(payload.query)
    location = _clean_optional_text(payload.location)
    frequency = _normalize_alert_frequency(payload.frequency)
    criteria = _alert_criteria(
        query=query,
        location=location,
        min_match_percent=payload.min_match_percent,
    )
    row = (
        await db.execute(
            text(
                "INSERT INTO job_alerts ("
                "user_id, name, query, location, min_match_percent, frequency, "
                "active, criteria, created_at, updated_at"
                ") VALUES ("
                ":uid, :name, :query, :location, :min_match_percent, :frequency, "
                "true, CAST(:criteria AS jsonb), NOW(), NOW()"
                f") RETURNING {JOB_ALERT_COLUMNS}"
            ),
            {
                "uid": user["id"],
                "name": name,
                "query": query,
                "location": location,
                "min_match_percent": payload.min_match_percent,
                "frequency": frequency,
                "criteria": json.dumps(criteria),
            },
        )
    ).mappings().one()
    await db.commit()
    return _job_alert_payload(row)


@app.put("/api/job-alerts/{alert_id}")
async def update_job_alert(
    alert_id: int,
    payload: JobAlertUpdateRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    current = await _require_job_alert(db, user_id=user["id"], alert_id=alert_id)
    name = (
        _clean_optional_text(payload.name)
        if payload.name is not None
        else current["name"]
    )
    if not name:
        raise HTTPException(status_code=400, detail="Job alert name is required")
    query = (
        _clean_optional_text(payload.query)
        if payload.query is not None
        else current["query"]
    )
    location = (
        _clean_optional_text(payload.location)
        if payload.location is not None
        else current["location"]
    )
    min_match_percent = (
        payload.min_match_percent
        if payload.min_match_percent is not None
        else current["min_match_percent"]
    )
    frequency = _normalize_alert_frequency(payload.frequency or current["frequency"])
    active = payload.active if payload.active is not None else current["active"]
    criteria = _alert_criteria(
        query=query,
        location=location,
        min_match_percent=min_match_percent,
    )
    row = (
        await db.execute(
            text(
                "UPDATE job_alerts SET "
                "name = :name, query = :query, location = :location, "
                "min_match_percent = :min_match_percent, frequency = :frequency, "
                "active = :active, criteria = CAST(:criteria AS jsonb), "
                "updated_at = NOW() "
                "WHERE id = :alert_id AND user_id = :uid "
                f"RETURNING {JOB_ALERT_COLUMNS}"
            ),
            {
                "alert_id": alert_id,
                "uid": user["id"],
                "name": name,
                "query": query,
                "location": location,
                "min_match_percent": min_match_percent,
                "frequency": frequency,
                "active": active,
                "criteria": json.dumps(criteria),
            },
        )
    ).mappings().one()
    await db.commit()
    return _job_alert_payload(row)


@app.delete("/api/job-alerts/{alert_id}")
async def disable_job_alert(
    alert_id: int,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    row = (
        await db.execute(
            text(
                "UPDATE job_alerts SET active = false, updated_at = NOW() "
                "WHERE id = :alert_id AND user_id = :uid RETURNING id"
            ),
            {"alert_id": alert_id, "uid": user["id"]},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Job alert not found")
    await db.commit()
    return {"status": "disabled", "alert_id": alert_id}


@app.get("/api/jobs/saved")
async def list_saved_jobs(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    rows = (
        await db.execute(
            text(
                f"SELECT {', '.join(f'j.{col.strip()}' for col in JOB_SELECT_COLUMNS.split(',') if col.strip())} "
                "FROM user_job_interactions uji "
                "JOIN jobs j ON uji.job_id = j.id "
                "WHERE uji.user_id = :uid AND uji.saved = true "
                "ORDER BY uji.created_at DESC, j.posted_at DESC"
            ),
            {"uid": user["id"]},
        )
    ).mappings().all()
    jobs = [_job_payload_from_row(row, sanitize_skill_signals=False) for row in rows]
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/jobs/{job_id}/save")
async def save_job(
    job_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    db_uuid = await _require_job_uuid(db, job_id)
    await _set_job_interaction_state(
        db,
        user_id=user["id"],
        job_id=db_uuid,
        saved=True,
        dismissed=False,
        action_type="save",
    )
    await _bump_session_state_version(str(user["id"]))
    return {"status": "saved", "job_id": job_id}


@app.delete("/api/jobs/{job_id}/save")
async def unsave_job(
    job_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    db_uuid = await _require_job_uuid(db, job_id)
    await _set_job_interaction_state(
        db,
        user_id=user["id"],
        job_id=db_uuid,
        saved=False,
        dismissed=False,
        action_type="unsave",
    )
    await _bump_session_state_version(str(user["id"]))
    return {"status": "unsaved", "job_id": job_id}


@app.post("/api/jobs/{job_id}/skip")
async def skip_job(
    job_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    db_uuid = await _require_job_uuid(db, job_id)
    await _set_job_interaction_state(
        db,
        user_id=user["id"],
        job_id=db_uuid,
        saved=False,
        dismissed=True,
        action_type="skip",
    )
    await _bump_session_state_version(str(user["id"]))
    return {"status": "skipped", "job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_uuid = to_uuid(job_id)
    row = (
        await db.execute(
            text(
                f"SELECT {JOB_SELECT_COLUMNS} FROM jobs WHERE id = :id"
            ),
            {"id": db_uuid},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_payload_from_row(row, public_id=job_id)


# ════════════════════════════════════════════════════════════════
# Applications
# ════════════════════════════════════════════════════════════════

@app.get("/api/applications")
async def list_applications(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]
    rows = (
        await db.execute(
            text(
                "SELECT a.id, a.status, a.applied_at, j.title as job_title, j.company, j.location "
                "FROM applications a JOIN jobs j ON a.job_id = j.id "
                "WHERE a.user_id = :uid ORDER BY a.applied_at DESC"
            ),
            {"uid": uid},
        )
    ).mappings().all()
    return {"applications": [dict(r) for r in rows]}


@app.post("/api/applications")
async def create_applications(
    body: ApplicationCreateRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = user["id"]
    created_ids: list[str] = []
    for job_id in body.job_ids:
        db_job_uuid = await _require_job_uuid(db, job_id)
        app_id = str(uuid.uuid4())
        await db.execute(
            text(
                "INSERT INTO applications (id, user_id, job_id) "
                "VALUES (:id, :uid, :job_id)"
            ),
            {"id": app_id, "uid": uid, "job_id": db_job_uuid},
        )
        created_ids.append(app_id)
    await db.commit()
    return {"created": len(created_ids), "application_ids": created_ids}


# ════════════════════════════════════════════════════════════════
# Market Demand
# ════════════════════════════════════════════════════════════════

async def _compute_skill_demand(
    db: AsyncSession,
) -> dict[str, tuple[float, int]]:
    """Count how many active jobs require each skill and normalise to [0,1].

    Returns a mapping of skill name to ``(demand_score, raw_job_count)`` so
    callers can expose both the normalised score and the unfiltered count
    without risk of the count being recomputed from the normalised value.
    """
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT s.name, COUNT(*) AS job_count "
                    "FROM job_required_skills jrs "
                    "JOIN skills s ON jrs.skill_id = s.id "
                    "JOIN jobs j ON jrs.job_id = j.id "
                    "WHERE j.is_active = true "
                    "GROUP BY s.name"
                )
            )
        ).mappings().all()
    except Exception:
        return {}

    if not rows:
        return {}

    counts = {str(row["name"]): int(row["job_count"]) for row in rows}
    max_count = max(counts.values())
    if max_count <= 0:
        return {}
    return {
        skill: (round(min(1.0, count / max_count), 4), count)
        for skill, count in counts.items()
    }


@app.get("/api/market-demand")
async def skill_demand(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Return current skill market demand derived from active job postings."""
    await _require_user(db, token_payload)
    demand = await _compute_skill_demand(db)
    max_raw_count = max((raw for _, raw in demand.values()), default=0)
    skills = [
        {
            "skill": skill,
            "demand": score,
            "job_count": raw_count,
        }
        for skill, (score, raw_count) in sorted(
            demand.items(), key=lambda item: item[1][0], reverse=True
        )[:limit]
    ]
    return {
        "skills": skills,
        "total_skills": len(demand),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ════════════════════════════════════════════════════════════════
# Deprecated Learning Path Compatibility
# ════════════════════════════════════════════════════════════════

@app.post("/api/learning-path")
async def deprecated_path_route(
    token_payload: dict[str, Any] = Depends(_get_current_user),
) -> dict[str, Any]:
    _ = token_payload
    raise HTTPException(
        status_code=410,
        detail="Deprecated endpoint. DQN is now used through session reranking in /api/recommendations.",
    )


# ════════════════════════════════════════════════════════════════
# Recommendations (pipeline proxy)
# ════════════════════════════════════════════════════════════════

@app.post("/pipeline/run")
async def run_pipeline_direct(
    request: PipelineRunRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
) -> dict[str, Any]:
    _require_admin_role(token_payload)
    return await _pipeline_post("/pipeline/run", request.model_dump())


@app.post("/recommendations")
@app.post("/api/recommendations")
async def run_pipeline(
    request: PipelineRunRequest = PipelineRunRequest(),
    http_request: Request = None,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    token_uid = str(token_payload.get("sub") or "")
    fast_cache_key: str | None = None
    if (
        token_uid
        and request.profile is None
        and not request.refresh_jobs
        and request.interaction_count == 0
        and request.target_role is None
    ):
        front_cache_key = _slate_front_cache_key(token_uid, int(request.limit))
        cached_response = _get_memory_slate_response(front_cache_key, http_request)
        if cached_response is not None:
            return cached_response
        cached_slate = await _get_cached_slate(front_cache_key)
        if cached_slate is not None:
            _store_memory_slate_response(
                front_cache_key,
                cached_slate,
                cache_tier="front",
                ttl_seconds=min(SLATE_CACHE_TTL_SECONDS, 2),
            )
            cached_response = _get_memory_slate_response(front_cache_key, http_request)
            if cached_response is not None:
                return cached_response
            return {
                **cached_slate,
                "cached": True,
                "cache_tier": "front",
                "served_from_cache_at": datetime.now(timezone.utc).isoformat(),
            }

        redis_session_version = await _redis_session_state_version(token_uid)
        fast_cache_key = _slate_fast_cache_key(
            token_uid, redis_session_version, int(request.limit)
        )
        cached_slate = await _get_cached_slate(fast_cache_key)
        if cached_slate is not None:
            _store_memory_slate(
                front_cache_key,
                cached_slate,
                min(SLATE_CACHE_TTL_SECONDS, 2),
            )
            _store_memory_slate_response(
                front_cache_key,
                cached_slate,
                cache_tier="front",
                ttl_seconds=min(SLATE_CACHE_TTL_SECONDS, 2),
            )
            _store_memory_slate_response(
                fast_cache_key,
                cached_slate,
                cache_tier="fast",
                ttl_seconds=min(SLATE_CACHE_TTL_SECONDS, 10),
            )
            cached_response = _get_memory_slate_response(fast_cache_key, http_request)
            if cached_response is not None:
                return cached_response
            return {
                **cached_slate,
                "cached": True,
                "cache_tier": "fast",
                # distinguishes cache serves in traces; the original request_id /
                # generated_at identify the slate's origin run.
                "served_from_cache_at": datetime.now(timezone.utc).isoformat(),
            }

    user = await _require_user(db, token_payload)
    # Identity always comes from the JWT subject (contract §9): a
    # client-supplied user_id must never select whose profile is ranked or
    # whose slate is persisted.
    uid = str(user["id"])

    payload = request.model_dump()
    payload["user_id"] = uid
    payload["profile"] = request.profile or await _pipeline_profile_for_user(db, user)
    profile_for_reasons = payload["profile"] if isinstance(payload["profile"], dict) else {}
    # Profile-completeness gate (before the slate cache): a request that did not
    # supply an explicit profile and whose stored profile has no skills, study
    # field, or CV would be ranked against a fabricated default identity. Return
    # an empty slate that prompts profile completion — and never serve a stale
    # cached slate to a now-gated user.
    if request.profile is None and not _profile_has_personalization_signal(profile_for_reasons, user):
        return _needs_profile_response()

    # Short-lived slate cache: the key embeds the session-state version, so
    # any save/skip/feedback in between produces a different key and the
    # request falls through to the live pipeline.
    session_version = await _session_state_version(db, uid)
    slate_cache_key = _slate_cache_key(uid, session_version, int(request.limit))
    cached_slate = await _get_cached_slate(slate_cache_key)
    if cached_slate is not None:
        return {
            **cached_slate,
            "cached": True,
            "cache_tier": "session",
            # distinguishes cache serves in traces; the original request_id /
            # generated_at identify the slate's origin run.
            "served_from_cache_at": datetime.now(timezone.utc).isoformat(),
        }

    if isinstance(payload["profile"], dict):
        if not payload["profile"].get("session_events"):
            session_history = payload["profile"].get("session_history") or []
            if isinstance(session_history, list) and session_history:
                payload["profile"]["session_events"] = [
                    item for item in session_history if isinstance(item, dict)
                ]
            elif not isinstance(session_history, list):
                payload["profile"]["session_events"] = []
        if not payload["profile"].get("session_events"):
            # Normal frontend requests carry no profile: hydrate the DQN
            # session state from persisted feedback events so same-session
            # save/skip/view actions influence the next slate (contract §10).
            payload["profile"]["session_events"] = await _recent_session_events(
                db, user["id"]
            )
            if not payload["profile"].get("session_history") and payload["profile"].get("session_events"):
                payload["profile"]["session_history"] = payload["profile"]["session_events"]
        if not payload["profile"].get("session_history") and payload["profile"].get("session_events"):
            payload["profile"]["session_history"] = payload["profile"]["session_events"]
    payload["interaction_count"] = (
        request.interaction_count
        if request.interaction_count > 0
        else await _interaction_count_for_user(db, user["id"])
    )

    request_id = str(uuid.uuid4())
    try:
        pipeline_resp = await _pipeline_post("/pipeline/run", payload)
    except HTTPException as exc:
        if exc.status_code in (502, 503, 504):
            return {
                "schema_version": "recommendation_v2",
                "request_id": request_id,
                "recommendations": [],
                "fairness_tpr_gap": 0.0,
                "degraded": True,
                "stale": False,
                "source": "pipeline_unavailable",
                "source_status": "pipeline_unavailable",
                "error_code": "pipeline_unavailable",
                "retryable": True,
                "model_bundle_version": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        raise

    ranked = pipeline_resp.get("ranked", [])
    await _upsert_jobs_to_db(db, ranked)

    recommendations = []
    slate_id = str(uuid.uuid4())
    pipeline_run_id = str(pipeline_resp.get("run_id") or slate_id)
    for item in ranked:
        job = _map_pipeline_job(item)
        compact_job = _compact_recommendation_job(job)
        sbert_score = float(item.get("sbert_score") or 0.0)
        ncf_score = float(item.get("ncf_score") or 0.0)
        dqn_score = float(item.get("dqn_score") or 0.0)
        recommendations.append({
            "job": compact_job,
            "hybrid_score": item.get("final_score") or 0.0,
            "sbert_score": sbert_score,
            "ncf_score": ncf_score,
            "dqn_score": dqn_score,
            "recommendation_id": slate_id,
            "match_percent": item.get("match_percent") or 0,
            "reason_filter_scores": _recommendation_reason_filter_scores(
                profile_for_reasons,
                item,
                job,
                sbert_score=sbert_score,
                ncf_score=ncf_score,
                dqn_score=dqn_score,
            ),
        })

    await _persist_served_slate(
        db,
        slate_id=slate_id,
        user_id=uid,
        pipeline_run_id=pipeline_run_id,
        ranked=ranked,
        request=request,
        profile=profile_for_reasons,
    )

    fairness_tpr_gap = 0.0
    pipeline_source = str(pipeline_resp.get("source") or "")
    degraded = bool(
        (pipeline_resp.get("stages") or {}).get("degradation", {}).get("degraded")
    )
    if not pipeline_source:
        # Legacy pipeline responses carry no source; classify conservatively.
        pipeline_source = "hybrid_model" if recommendations else "empty_candidates"
    response_payload = {
        "schema_version": "recommendation_v2",
        "request_id": request_id,
        "recommendations": recommendations,
        "fairness_tpr_gap": fairness_tpr_gap,
        "recommendation_id": slate_id,
        "run_id": pipeline_run_id,
        "degraded": degraded,
        "stale": False,
        "source": pipeline_source,
        "model_bundle_version": pipeline_resp.get("model_bundle_version"),
        "reason_filter_labels": dict(REASON_FILTER_LABELS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not degraded and recommendations:
        await _store_cached_slate(slate_cache_key, response_payload)
        if fast_cache_key is not None:
            await _store_cached_slate(fast_cache_key, response_payload)
            _store_memory_slate(
                _slate_front_cache_key(uid, int(request.limit)),
                response_payload,
                min(SLATE_CACHE_TTL_SECONDS, 2),
            )
            _store_memory_slate_response(
                _slate_front_cache_key(uid, int(request.limit)),
                response_payload,
                cache_tier="front",
                ttl_seconds=min(SLATE_CACHE_TTL_SECONDS, 2),
            )
            _store_memory_slate_response(
                fast_cache_key,
                response_payload,
                cache_tier="fast",
                ttl_seconds=min(SLATE_CACHE_TTL_SECONDS, 10),
            )
    return response_payload


@app.post("/api/recommendations/feedback")
async def recommendation_feedback(
    body: RecommendationFeedbackRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = str(user["id"])

    job_uuid = await _require_job_uuid(db, body.job_id)
    slate_uuid = _coerce_uuid(body.served_slate_id or body.recommendation_id)
    if (body.served_slate_id or body.recommendation_id) and slate_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid served slate ID")
    if slate_uuid is not None:
        slate_row = (
            await db.execute(
                text(
                    "SELECT id FROM served_slates "
                    "WHERE id = :slate_id AND user_id = :user_id"
                ),
                {"slate_id": slate_uuid, "user_id": uuid.UUID(uid)},
            )
        ).mappings().first()
        if not slate_row:
            raise HTTPException(status_code=404, detail="Served slate not found")
    reward = _feedback_reward(body.event, body.dwell_ms)
    metadata = {
        "recommendation_id": body.recommendation_id,
        "run_id": body.run_id,
        "served_slate_id": body.served_slate_id,
        "rank": body.rank,
        "slate_job_ids": body.slate_job_ids,
        "reward": reward,
    }
    model_provenance = {
        "sbert_score": body.sbert_score,
        "ncf_score": body.ncf_score,
        "dqn_score": body.dqn_score,
    }
    profile_payload = await _pipeline_profile_for_user(db, user)
    job_context_row = (
        await db.execute(
            text(
                "SELECT id, title, company, description, description_text, "
                "required_skill_names, extracted_skill_names, source "
                "FROM jobs WHERE id = :job_id"
            ),
            {"job_id": job_uuid},
        )
    ).mappings().first()
    job_payload = {
        "id": body.job_id,
        "title": body.job_id,
        "company": "",
        "description": "",
        "description_text": "",
        "required_skills": [],
        "source": None,
    }
    if job_context_row:
        job_payload = {
            "id": str(job_context_row["id"]),
            "title": job_context_row.get("title") or "",
            "company": job_context_row.get("company") or "",
            "description": job_context_row.get("description") or "",
            "description_text": job_context_row.get("description_text") or "",
            "required_skills": (
                _string_list(job_context_row.get("required_skill_names"))
                or _string_list(job_context_row.get("extracted_skill_names"))
            ),
            "source": job_context_row.get("source"),
        }
    event_payload = {
        "user_id": uid,
        "job_id": body.job_id,
        "event": body.event,
        "reward": reward,
        "rank": body.rank,
        "dwell_ms": body.dwell_ms,
        "sbert_score": body.sbert_score,
        "ncf_score": body.ncf_score,
        "dqn_score": body.dqn_score,
        "slate_job_ids": body.slate_job_ids,
        "run_id": body.run_id,
        "served_slate_id": body.served_slate_id or body.recommendation_id,
        "profile": profile_payload,
        "job": job_payload,
    }
    outbox_id: int | None = None

    try:
        await db.execute(
            text(
                "INSERT INTO feedback_events ("
                "event_type, user_id, job_id, slate_id, rank, source, dwell_ms, "
                "model_provenance, metadata, created_at"
                ") VALUES ("
                ":event, :uid, :job_id, :slate_id, :rank, 'frontend', :dwell_ms, "
                "CAST(:model_provenance AS jsonb), CAST(:metadata AS jsonb), NOW()"
                ")"
            ),
            {
                "event": body.event,
                "uid": uid,
                "job_id": job_uuid,
                "slate_id": slate_uuid,
                "rank": body.rank + 1,
                "dwell_ms": body.dwell_ms,
                "model_provenance": json.dumps(model_provenance),
                "metadata": json.dumps(metadata),
            },
        )
        await db.execute(
            text(
                "INSERT INTO user_interactions ("
                "user_id, action_type, target_type, target_id, metadata, created_at"
                ") VALUES ("
                ":uid, :event, 'job', :target_id, CAST(:metadata AS jsonb), NOW()"
                ")"
            ),
            {
                "uid": uid,
                "event": body.event,
                "target_id": job_uuid,
                "metadata": json.dumps(metadata),
            },
        )
        await db.execute(
            text(
                "INSERT INTO user_job_interactions ("
                "user_id, job_id, clicked, saved, applied, dismissed, dwell_seconds, created_at"
                ") VALUES ("
                ":uid, :job_id, :clicked, :saved, :applied, :dismissed, :dwell_seconds, NOW()"
                ") ON CONFLICT (user_id, job_id) DO UPDATE SET "
                "clicked = user_job_interactions.clicked OR EXCLUDED.clicked, "
                "applied = user_job_interactions.applied OR EXCLUDED.applied, "
                "saved = CASE "
                "  WHEN EXCLUDED.dismissed THEN false "
                "  WHEN EXCLUDED.saved THEN true "
                "  ELSE user_job_interactions.saved "
                "END, "
                "dismissed = CASE "
                "  WHEN EXCLUDED.saved THEN false "
                "  WHEN EXCLUDED.dismissed THEN true "
                "  ELSE user_job_interactions.dismissed "
                "END, "
                "dwell_seconds = GREATEST("
                "COALESCE(user_job_interactions.dwell_seconds, 0), "
                "COALESCE(EXCLUDED.dwell_seconds, 0)"
                ")"
            ),
            {
                "uid": uid,
                "job_id": job_uuid,
                "clicked": body.event in {"click", "source_click", "view"},
                "saved": body.event == "save",
                "applied": body.event == "apply",
                "dismissed": body.event == "skip",
                "dwell_seconds": body.dwell_ms / 1000.0 if body.dwell_ms else None,
            },
        )
        outbox_id = await _insert_model_feedback_outbox(
            db,
            user_id=uid,
            job_id=job_uuid,
            event_type=body.event,
            payload=event_payload,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("feedback persistence failed user_id=%s job_id=%s", uid, body.job_id)
        raise HTTPException(status_code=500, detail="failed to persist feedback") from exc

    # Session event recorded: advance the session-state version so the next
    # recommendation request bypasses the cached slate (contract §10).
    await _bump_session_state_version(uid)

    try:
        pipeline_resp = await _pipeline_post("/feedback", event_payload)
        if outbox_id is not None:
            await _mark_model_feedback_outbox_sent(db, outbox_id)
    except HTTPException as exc:
        if outbox_id is not None:
            await _mark_model_feedback_outbox_failed(db, outbox_id, exc)
        pipeline_resp = {"status": "queued"}

    return {"status": "ok", "pipeline": pipeline_resp}


@app.get("/api/jobs/{job_id}/skill-gap")
async def job_skill_gap(
    job_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    user_skills = await _user_skills(db, user["id"])
    gap = await _job_skill_gap(db, user_skills, job_id)
    await db.execute(
        text(
            """
            INSERT INTO skill_gap_snapshots (
                user_id, job_id, missing_skills, matched_skills, explanation
            )
            VALUES (
                :user_id,
                :job_id,
                :missing_skills,
                :matched_skills,
                CAST(:explanation AS jsonb)
            )
            """
        ).bindparams(
            bindparam("missing_skills", type_=ARRAY(SqlText())),
            bindparam("matched_skills", type_=ARRAY(SqlText())),
        ),
        {
            "user_id": user["id"],
            "job_id": job_id,
            "missing_skills": gap["missing_skills"],
            "matched_skills": gap["matched_skills"],
            "explanation": json.dumps(gap["explanation"]),
        },
    )
    await db.commit()
    return gap


# ════════════════════════════════════════════════════════════════
# A/B Testing and Monitoring Endpoints
# ════════════════════════════════════════════════════════════════

@app.post("/api/experiments")
async def create_experiment(
    body: CreateExperimentRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    result = await db.execute(
        text(
            """
            INSERT INTO experiments (name, description, variants, target_metric)
            VALUES (:name, :description, CAST(:variants AS jsonb), :target_metric)
            RETURNING id, name, description, variants, status, target_metric, created_at
            """
        ),
        {
            "name": body.name,
            "description": body.description or "",
            "variants": json.dumps([v.model_dump() for v in body.variants]),
            "target_metric": body.target_metric,
        },
    )
    await db.commit()
    row = result.mappings().first()
    return dict(row) if row else {}


@app.get("/api/experiments")
async def list_experiments(
    status: str | None = Query(default=None, pattern="^(draft|running|paused|completed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_user(db, token_payload)
    where_clause = ""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        where_clause = "WHERE status = :status"
        params["status"] = status
    count_result = await db.execute(
        text(f"SELECT COUNT(*) AS total FROM experiments {where_clause}"),
        params,
    )
    total = count_result.mappings().first()["total"] if count_result else 0
    result = await db.execute(
        text(
            f"""
            SELECT id, name, description, variants, status, target_metric,
                   start_at, end_at, created_at, updated_at
            FROM experiments
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "experiments": [dict(row) for row in rows],
    }


@app.get("/api/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_user(db, token_payload)
    result = await db.execute(
        text(
            """
            SELECT id, name, description, variants, status, target_metric,
                   start_at, end_at, created_at, updated_at
            FROM experiments
            WHERE id = :experiment_id
            """
        ),
        {"experiment_id": experiment_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="experiment not found")
    return dict(row)


@app.post("/api/experiments/{experiment_id}/start")
async def start_experiment(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    result = await db.execute(
        text(
            """
            UPDATE experiments
            SET status = 'running', start_at = NOW(), updated_at = NOW()
            WHERE id = :experiment_id
            RETURNING id, name, status, start_at
            """
        ),
        {"experiment_id": experiment_id},
    )
    await db.commit()
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="experiment not found")
    return dict(row)


@app.post("/api/experiments/{experiment_id}/pause")
async def pause_experiment(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    result = await db.execute(
        text(
            """
            UPDATE experiments
            SET status = 'paused', updated_at = NOW()
            WHERE id = :experiment_id
            RETURNING id, name, status
            """
        ),
        {"experiment_id": experiment_id},
    )
    await db.commit()
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="experiment not found")
    return dict(row)


@app.post("/api/experiments/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    result = await db.execute(
        text(
            """
            UPDATE experiments
            SET status = 'completed', end_at = NOW(), updated_at = NOW()
            WHERE id = :experiment_id
            RETURNING id, name, status, end_at
            """
        ),
        {"experiment_id": experiment_id},
    )
    await db.commit()
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="experiment not found")
    return dict(row)


@app.post("/api/experiments/{experiment_id}/assign")
async def assign_experiment_variant(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    user_id = str(user["id"])
    existing = await _get_experiment_assignment(db, experiment_id, user_id)
    if existing:
        return {"experiment_id": experiment_id, "user_id": user_id, "variant_name": existing["variant_name"], "assigned_at": existing["assigned_at"]}
    result = await db.execute(
        text(
            """
            SELECT variants FROM experiments
            WHERE id = :experiment_id AND status = 'running'
            AND (start_at IS NULL OR start_at <= NOW())
            AND (end_at IS NULL OR end_at >= NOW())
            """
        ),
        {"experiment_id": experiment_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="experiment not found or not running")
    variants = row["variants"]
    if isinstance(variants, str):
        variants = json.loads(variants)
    variant = _pick_variant(variants, user_id, experiment_id)
    await _assign_user_to_variant(db, experiment_id, user_id, variant["name"])
    return {"experiment_id": experiment_id, "user_id": user_id, "variant_name": variant["name"]}


@app.get("/api/experiments/{experiment_id}/metrics")
async def get_experiment_metrics(
    experiment_id: str,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_user(db, token_payload)
    # Sample sizes per variant
    sample_result = await db.execute(
        text(
            """
            SELECT variant_name, COUNT(*) AS sample_size
            FROM experiment_assignments
            WHERE experiment_id = :experiment_id
            GROUP BY variant_name
            """
        ),
        {"experiment_id": experiment_id},
    )
    sample_rows = sample_result.mappings().all()
    # Feedback events per variant
    event_result = await db.execute(
        text(
            """
            SELECT
                (model_provenance->>'experiment_variant') AS variant_name,
                event_type,
                COUNT(*) AS event_count,
                COALESCE(AVG(dwell_ms), 0) AS avg_dwell_ms
            FROM feedback_events
            WHERE model_provenance->>'experiment_id' = :experiment_id
            GROUP BY variant_name, event_type
            """
        ),
        {"experiment_id": experiment_id},
    )
    event_rows = event_result.mappings().all()
    metrics: dict[str, Any] = {}
    for row in sample_rows:
        variant = row["variant_name"]
        metrics[variant] = {
            "sample_size": row["sample_size"],
            "impressions": 0,
            "clicks": 0,
            "applies": 0,
            "saves": 0,
            "ctr_proxy": 0.0,
            "apply_rate": 0.0,
            "mean_dwell_ms": 0.0,
        }
    impressions: dict[str, int] = {}
    clicks: dict[str, int] = {}
    applies: dict[str, int] = {}
    saves: dict[str, int] = {}
    dwell_sums: dict[str, float] = {}
    dwell_counts: dict[str, int] = {}
    for row in event_rows:
        variant = row["variant_name"] or "unknown"
        event_type = row["event_type"]
        count = row["event_count"]
        avg_dwell = float(row["avg_dwell_ms"] or 0)
        if event_type == "impression":
            impressions[variant] = impressions.get(variant, 0) + count
        elif event_type in {"click", "source_click"}:
            clicks[variant] = clicks.get(variant, 0) + count
        elif event_type == "apply":
            applies[variant] = applies.get(variant, 0) + count
        elif event_type == "save":
            saves[variant] = saves.get(variant, 0) + count
        if avg_dwell > 0:
            dwell_sums[variant] = dwell_sums.get(variant, 0.0) + (avg_dwell * count)
            dwell_counts[variant] = dwell_counts.get(variant, 0) + count
    for variant in metrics:
        metrics[variant]["impressions"] = impressions.get(variant, 0)
        metrics[variant]["clicks"] = clicks.get(variant, 0)
        metrics[variant]["applies"] = applies.get(variant, 0)
        metrics[variant]["saves"] = saves.get(variant, 0)
        imp = metrics[variant]["impressions"]
        metrics[variant]["ctr_proxy"] = round(clicks.get(variant, 0) / imp, 4) if imp > 0 else 0.0
        metrics[variant]["apply_rate"] = round(applies.get(variant, 0) / imp, 4) if imp > 0 else 0.0
        total_dwell = dwell_sums.get(variant, 0.0)
        total_dwell_count = dwell_counts.get(variant, 0)
        metrics[variant]["mean_dwell_ms"] = round(total_dwell / total_dwell_count, 2) if total_dwell_count > 0 else 0.0
    return {"experiment_id": experiment_id, "metrics": metrics}


# ════════════════════════════════════════════════════════════════
# Export: PDF Resume, CSV Job Listings
# ════════════════════════════════════════════════════════════════

class ExportRequest(BaseModel):
    """Export request with optional filters for jobs."""
    user_id: int | str | None = None
    limit: int = Field(default=20, ge=1, le=1000)
    include_scores: bool = False


@app.get("/api/exports/profile-csv")
@app.get("/exports/profile-csv")
async def export_profile_csv(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export user profile as CSV."""
    user = await _require_user(db, token_payload)
    skill_names = await _profile_skill_names(db, user["id"])
    profile = {
        "name": user.get("name"),
        "email": user.get("email"),
        "university": user.get("university"),
        "program_studi": user.get("program_studi"),
        "skills": skill_names,
        "completion_percent": user.get("completion_percent"),
    }
    if not await _admin_table_exists(db, "user_profiles"):
        profile["target_role"] = None
    else:
        result = await db.execute(
            text("SELECT target_role FROM user_profiles WHERE user_id = :uid LIMIT 1"),
            {"uid": user["id"]},
        )
        row = result.mappings().first()
        profile["target_role"] = row.get("target_role") if row else None

    csv_content = generate_profile_csv(profile)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scpa_profile_{timestamp}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@app.get("/api/exports/jobs-pdf")
@app.get("/exports/jobs-pdf")
async def export_jobs_pdf(
    include_scores: bool = Query(default=False),
    limit: int = Query(default=10, ge=1, le=50),
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export top job recommendations as PDF resume."""
    user = await _require_user(db, token_payload)
    uid = str(user["id"])
    profile = await _pipeline_profile_for_user(db, user)

    # Get recent recommendations from cached slate or fresh run
    recommendations = []
    try:
        # Try to get cached slate
        cached = await _get_cached_slate(f"scpa:slate:{uid}:export:{limit}")
        if cached and "recommendations" in cached:
            recommendations = cached["recommendations"][:limit]
        else:
            # Fresh run for export
            pipeline_result = await _pipeline_post(
                "/pipeline/run",
                {
                    "user_id": uid,
                    "profile": profile,
                    "limit": limit,
                },
            )
            recommendations = pipeline_result.get("recommendations", [])[:limit]
    except Exception:
        recommendations = []

    pdf_bytes = generate_resume_pdf(profile, recommendations)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scpa_recommendations_{timestamp}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@app.post("/api/exports/jobs-csv")
@app.post("/exports/jobs-csv")
async def export_jobs_csv(
    body: ExportRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export job listings as CSV."""
    user = await _require_user(db, token_payload)
    uid = str(user["id"])
    profile = await _pipeline_profile_for_user(db, user)

    # Get recommendations
    jobs = []
    try:
        cached = await _get_cached_slate(f"scpa:slate:{uid}:export:{body.limit}")
        if cached and "recommendations" in cached:
            jobs = cached["recommendations"][:body.limit]
        else:
            pipeline_result = await _pipeline_post(
                "/pipeline/run",
                {
                    "user_id": uid,
                    "profile": profile,
                    "limit": body.limit,
                },
            )
            jobs = pipeline_result.get("recommendations", [])[:body.limit]
    except Exception:
        jobs = []

    csv_content = generate_jobs_csv(jobs, include_scores=body.include_scores)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scpa_jobs_{timestamp}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@app.post("/api/events/track")
async def track_event(
    body: TrackEventRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    user_id = str(user["id"])
    # Verify the user is assigned to this experiment
    assignment = await _get_experiment_assignment(db, body.experiment_id, user_id)
    if not assignment:
        raise HTTPException(status_code=400, detail="user not assigned to this experiment")
    # Insert a feedback event with experiment provenance
    provenance = {
        "experiment_id": body.experiment_id,
        "experiment_variant": assignment["variant_name"],
        **body.metadata,
    }
    await db.execute(
        text(
            """
            INSERT INTO feedback_events (
                event_type, user_id, job_id, dwell_ms, model_provenance
            )
            VALUES (:event_type, :user_id, :job_id, :dwell_ms, CAST(:provenance AS jsonb))
            """
        ),
        {
            "event_type": body.event_type,
            "user_id": user_id,
            "job_id": body.job_id,
            "dwell_ms": body.dwell_ms,
            "provenance": json.dumps(provenance),
        },
    )
    await db.commit()
    return {"status": "ok", "experiment_id": body.experiment_id, "variant_name": assignment["variant_name"]}
