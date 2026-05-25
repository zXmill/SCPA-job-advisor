"""SCPA API Gateway — public-facing FastAPI service."""

from __future__ import annotations

import logging
import asyncio
import io
import os
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
from sqlalchemy import Text as SqlText
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

try:
    from services.pipeline.pipeline.extractors.skills import SKILL_ALIASES
except ImportError:  # pragma: no cover - only used in minimal gateway deployments
    SKILL_ALIASES = {
        "Python": {"python", "py"},
        "SQL": {"sql"},
        "English": {"english", "bahasa inggris"},
    }

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover - optional PDF extraction
    PdfReader = None

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("scpa.gateway")

# ── Configuration ──
DEFAULT_DEV_CORS_ORIGINS = ("http://localhost:3000", "http://localhost:8000")
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
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))
HEALTH_TIMEOUT_SECONDS = float(os.getenv("HEALTH_TIMEOUT_SECONDS", "2"))
P95_TARGET_MS = int(os.getenv("GATEWAY_P95_TARGET_MS", "150"))
PUBLIC_GATEWAY_URL = os.getenv("PUBLIC_GATEWAY_URL", "http://localhost:8000").rstrip("/")
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
    "career_signal": "Highest DQN career-path signal",
    "location_fit": "Closest profile location",
    "recency": "Newest jobs",
}
REASON_FILTER_RECENCY_WINDOW_DAYS = 30.0

# ── CV Upload ──
CV_UPLOAD_DIR = Path(os.getenv("CV_UPLOAD_DIR", "data/uploads/cv"))
MAX_CV_SIZE_MB = int(os.getenv("MAX_CV_SIZE_MB", "5"))
MAX_CV_SIZE_BYTES = MAX_CV_SIZE_MB * 1024 * 1024
CV_ALLOWED_EXTENSIONS = {".pdf", ".txt"}

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

SKILL_SEARCH_MAX_ROWS = 500


def _default_skill_category(skill_name: str) -> str:
    lower = skill_name.lower()
    if lower in {"english"}:
        return "linguistic"
    if lower in {"public speaking"}:
        return "soft"
    return "technical"


DEFAULT_SKILL_TAXONOMY: tuple[dict[str, Any], ...] = tuple(
    {
        "name": name,
        "category": _default_skill_category(name),
        "aliases": sorted({str(alias).lower() for alias in aliases}),
    }
    for name, aliases in sorted(SKILL_ALIASES.items())
)

_SEED_SKILL_STMT = text(
    """
    INSERT INTO skills (name, category, aliases, frequency, updated_at)
    VALUES (:name, :category, :aliases, 1, NOW())
    ON CONFLICT (name) DO UPDATE SET
        category = EXCLUDED.category,
        aliases = EXCLUDED.aliases,
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


class SkillSearchItem(BaseModel):
    id: str
    name: str
    category: str
    aliases: list[str] = Field(default_factory=list)


class SkillSearchResponse(BaseModel):
    skills: list[SkillSearchItem]


PROFILE_COMPLETENESS_ITEMS = (
    {"id": "name", "label": "Nama lengkap"},
    {"id": "program_studi", "label": "Program studi"},
    {"id": "university", "label": "Universitas"},
    {"id": "skills", "label": "Keahlian"},
)


class PipelineRunRequest(BaseModel):
    user_id: int | str | None = None
    refresh_jobs: bool = False
    profile: dict[str, Any] | None = None
    interaction_count: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    target_role: str | None = Field(default=None, min_length=1)


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


def _job_has_indonesia_signal(job: dict[str, Any]) -> bool:
    host = urlparse(str(job.get("source_url") or "")).hostname or ""
    if host.lower() in INDONESIA_JOB_HOSTS:
        return True
    haystack = " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "description", "source_url")
    ).lower()
    return any(term in haystack for term in INDONESIA_JOB_TERMS)


async def _upsert_jobs_to_db(db: AsyncSession, ranked: list[dict[str, Any]]) -> None:
    """Bulk upsert recommended jobs into the database, handling ENUM mapping."""
    db_jobs_params = []
    for item in ranked:
        jid = str(item.get("id", ""))
        if not jid:
            continue
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
            "experience_level": clean_experience_level(item.get("experience_level")),
            "posted_at": item.get("posted_at") or datetime.now(),
            "source": clean_job_source(item.get("source")),
            "is_active": item.get("is_active", True),
            "match_data": json.dumps({
                "skills": item.get("skills") or item.get("tags") or [],
                "source_url": item.get("source_url") or item.get("url") or None,
            })
        })
    if not db_jobs_params:
        return
    try:
        await db.execute(
            text("""
                INSERT INTO jobs (
                    id, title, company, company_logo, location, type, min_salary, max_salary,
                    salary_currency, salary_text, employment_mode, description, experience_level,
                    posted_at, source, is_active, match_data
                ) VALUES (
                    :id, :title, :company, :company_logo, :location, :type, :min_salary, :max_salary,
                    :salary_currency, :salary_text, :employment_mode, :description, :experience_level,
                    :posted_at, :source, :is_active, :match_data
                ) ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    company_logo = EXCLUDED.company_logo,
                    location = EXCLUDED.location,
                    description = EXCLUDED.description,
                    salary_text = COALESCE(EXCLUDED.salary_text, jobs.salary_text),
                    source = EXCLUDED.source,
                    is_active = EXCLUDED.is_active,
                    match_data = EXCLUDED.match_data
            """),
            db_jobs_params
        )
        await db.commit()
    except Exception as e:
        logger.error("Failed to upsert recommended jobs: %s", e)
        await db.rollback()


def _map_pipeline_job(item: dict[str, Any]) -> dict[str, Any]:
    """Map pipeline job item to gateway-compatible Job dictionary."""
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
        "experience_level": item.get("experience_level") or None,
        "posted_at": item.get("posted_at") or None,
        "source": item.get("source") or None,
        "source_url": item.get("source_url") or item.get("url") or None,
        "skills": item.get("skills") or item.get("tags") or [],
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


def _admin_model_health_summary(pipeline_health: dict[str, Any]) -> dict[str, Any]:
    downstream = pipeline_health.get("downstream")
    downstream = downstream if isinstance(downstream, dict) else {}
    telemetry = pipeline_health.get("telemetry")
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    stages = telemetry.get("stages")
    stages = stages if isinstance(stages, dict) else {}

    def service_model(name: str, stage_name: str | None = None) -> dict[str, Any]:
        url = downstream.get(name)
        return {
            "status": "configured" if url else "unconfigured",
            "url": url,
            "stage": stages.get(stage_name or name, {}),
        }

    return {
        "status": pipeline_health.get("status", "unknown"),
        "pipeline": {
            "status": pipeline_health.get("status", "unknown"),
            "mode": pipeline_health.get("mode"),
            "p95_target_ms": pipeline_health.get("p95_target_ms"),
        },
        "models": {
            "scraper": service_model("scraper", "scrape"),
            "sbert": service_model("sbert"),
            "ncf": service_model("ncf"),
            "dqn": service_model("dqn"),
            "calibrator": {
                "status": "active" if "calibrator" in stages else "inactive",
                "stage": stages.get("calibrator", {}),
            },
            "aggregation": {
                "status": "active" if "aggregation" in stages else "inactive",
                "stage": stages.get("aggregation", {}),
            },
        },
        "telemetry": telemetry,
        "continual_training": pipeline_health.get("continual_training", {}),
    }


async def _require_user(db: AsyncSession, token_payload: dict[str, Any]) -> dict[str, Any]:
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    row = (
        await db.execute(
            text(
                "SELECT id, name, email, role, completion_percent, program_studi, university "
                "FROM users WHERE id = :id"
            ),
            {"id": user_id},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


def _normalise_skill_value(value: str) -> str:
    return " ".join(str(value).lower().strip().split())


async def _ensure_default_skill_taxonomy(db: AsyncSession) -> bool:
    """Seed the baseline controlled vocabulary if the taxonomy table exists."""

    try:
        table_exists = (
            await db.execute(text("SELECT to_regclass('public.skills')"))
        ).scalar_one()
        if table_exists is None:
            return False

        count = (await db.execute(text("SELECT COUNT(*) FROM skills"))).scalar_one()
        if int(count or 0) > 0:
            return True

        for row in DEFAULT_SKILL_TAXONOMY:
            await db.execute(_SEED_SKILL_STMT, row)
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
                "SELECT name, category, aliases "
                "FROM skills ORDER BY frequency DESC, name ASC "
                "LIMIT :limit"
            ),
            {"limit": SKILL_SEARCH_MAX_ROWS},
        )
    ).mappings().all()
    return [
        {
            "id": str(row["name"]),
            "name": str(row["name"]),
            "category": str(row["category"] or "technical"),
            "aliases": [str(alias) for alias in (row.get("aliases") or [])],
        }
        for row in rows
    ]


def _skill_search_score(skill: dict[str, Any], query: str) -> int:
    name = _normalise_skill_value(skill["name"])
    aliases = [_normalise_skill_value(alias) for alias in skill.get("aliases", [])]
    if query == name:
        return 0
    if query in aliases:
        return 1
    if name.startswith(query):
        return 2
    if any(alias.startswith(query) for alias in aliases):
        return 3
    if query in name:
        return 4
    if any(query in alias for alias in aliases):
        return 5
    return 99


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

    text_lower = raw_text.lower()
    found: dict[str, str] = {}

    # Try multi-word matches first to avoid partial overlaps.
    for term, canonical_name in multi_word_skills.items():
        if term in text_lower:
            found[canonical_name] = canonical_name

    # Then single-word token matches (strip trailing punctuation).
    _punctuation = str.maketrans("", "", '.,;:!?()[]{}"\'`/~@#$%^&*+=|<>')
    tokens = set()
    for word in text_lower.split():
        word = word.strip().translate(_punctuation)
        if word:
            tokens.add(_normalise_skill_value(word))
    for token in tokens:
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
        "program_studi": _has_profile_value(user.get("program_studi")),
        "university": _has_profile_value(user.get("university")),
        "skills": skill_count > 0,
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
    }


async def _pipeline_profile_for_user(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    skills = await _profile_skill_names(db, user["id"])
    return {
        "name": user.get("name"),
        "program_studi": user.get("program_studi"),
        "jurusan": user.get("program_studi"),
        "university": user.get("university"),
        "skills": skills,
    }


async def _resolve_target_role(db: AsyncSession, user: dict[str, Any], requested: str | None = None) -> str:
    if requested:
        return requested
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


async def _job_skill_gap(
    db: AsyncSession, user_skills: set[str], job_id: str
) -> dict[str, Any]:
    db_uuid = to_uuid(job_id)
    row = (
        await db.execute(
            text("SELECT title, company, match_data FROM jobs WHERE id = :id"),
            {"id": db_uuid},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    match_data = _parse_match_data(row.get("match_data"))
    required_skills = _display_skill_list(match_data.get("skills", []))
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
        "career_signal": _clamped_reason_score(dqn_score),
        "location_fit": _location_reason_score(profile, job),
        "recency": _recency_reason_score(item.get("posted_at") or job.get("posted_at")),
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
        matches.sort(key=lambda skill: (_skill_search_score(skill, query), skill["name"]))
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
        },
    }


@app.post("/api/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "SELECT id, name, email, password_hash, role, completion_percent, program_studi, university "
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

    if updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["id"] = uid
        await db.execute(
            text(f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = :id"),
            updates,
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
        await db.execute(
            text(
                "UPDATE users SET program_studi = :program_studi, university = :university, "
                "completion_percent = GREATEST(completion_percent, 30), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"program_studi": program_studi, "university": university, "id": uid},
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
        await db.execute(
            text(
                "UPDATE users SET completion_percent = GREATEST(completion_percent, 85), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": uid},
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


# ════════════════════════════════════════════════════════════════
# Jobs
# ════════════════════════════════════════════════════════════════

@app.get("/api/jobs")
async def list_jobs(
    location: str | None = None,
    experience: str | None = None,
    page: int = Query(default=1, ge=1, le=10_000),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Paginated job list.

    Returns ``{ jobs, total, page, limit, total_pages }``. Indonesia-only
    filtering is pushed into SQL so both COUNT and LIMIT queries are
    consistent and the frontend receives a stable page size.
    """
    conditions = ["is_active = true"]
    params: dict[str, Any] = {}
    if location:
        conditions.append("location ILIKE :location")
        params["location"] = f"%{location}%"
    if experience:
        conditions.append("experience_level = :experience")
        params["experience"] = experience

    # Known Indonesia job boards + location terms keep the candidate pool
    # Indonesia-focused. The scraper already enforces this; the guard here
    # ensures any stray non-Indonesia rows do not break pagination counts.
    _INDONESIA_SOURCES = ("kalibrr", "karir", "jobstreet", "glints", "techinasia", "linkedin")
    _INDONESIA_TERMS = ["indonesia", "jakarta", "surabaya", "bandung", "depok",
                        "tangerang", "bekasi", "bogor", "yogyakarta", "semarang",
                        "bali", "medan", "makassar", "batam", "subang", "jawa",
                        "kalimantan", "sumatra", "sulawesi"]
    indonesia_where = (
        f"(source IN {_INDONESIA_SOURCES} OR location ILIKE ANY(:indonesia_terms))"
    )
    params["indonesia_terms"] = [f"%{t}%" for t in _INDONESIA_TERMS]
    conditions.append(indonesia_where)

    where_clause = " AND ".join(conditions)

    offset = (page - 1) * limit
    params_with_paging = {**params, "limit": limit, "offset": offset}
    rows = (
        await db.execute(
            text(
                "SELECT id, title, company, company_logo, location, type, min_salary, max_salary, "
                "salary_currency, salary_text, employment_mode, description, experience_level, "
                "posted_at, source, is_active, match_data "
                f"FROM jobs WHERE {where_clause} ORDER BY posted_at DESC, id "
                "LIMIT :limit OFFSET :offset"
            ),
            params_with_paging,
        )
    ).mappings().all()
    total_row = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total FROM jobs WHERE {where_clause}"),
            params,
        )
    ).mappings().first()
    total = int((total_row or {}).get("total") or 0)
    jobs: list[dict[str, Any]] = []
    for row in rows:
        job = dict(row)
        match_data = _parse_match_data(job.pop("match_data", None))
        job["source_url"] = match_data.get("source_url")
        job["skills"] = match_data.get("skills") or []
        job["company_logo"] = _proxied_company_logo_url(job.get("company_logo"), job.get("company"))
        jobs.append(job)
    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


def _job_payload_from_row(row: Any, *, public_id: str | None = None) -> dict[str, Any]:
    job = dict(row)
    job["id"] = public_id or str(job["id"])
    match_data = _parse_match_data(job.pop("match_data", None))
    job["source_url"] = match_data.get("source_url")
    job["skills"] = match_data.get("skills") or []
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
) -> None:
    await db.execute(
        text(
            "INSERT INTO user_job_interactions ("
            "user_id, job_id, clicked, saved, applied, dismissed, created_at"
            ") VALUES ("
            ":uid, :job_id, false, :saved, false, :dismissed, NOW()"
            ") ON CONFLICT (user_id, job_id) DO UPDATE SET "
            "saved = EXCLUDED.saved, "
            "dismissed = EXCLUDED.dismissed"
        ),
        {"uid": user_id, "job_id": job_id, "saved": saved, "dismissed": dismissed},
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
                "SELECT j.id, j.title, j.company, j.company_logo, j.location, j.type, "
                "j.min_salary, j.max_salary, j.salary_currency, j.salary_text, "
                "j.employment_mode, j.description, j.experience_level, j.posted_at, "
                "j.source, j.is_active, j.match_data "
                "FROM user_job_interactions uji "
                "JOIN jobs j ON uji.job_id = j.id "
                "WHERE uji.user_id = :uid AND uji.saved = true "
                "ORDER BY uji.created_at DESC, j.posted_at DESC"
            ),
            {"uid": user["id"]},
        )
    ).mappings().all()
    jobs = [_job_payload_from_row(row) for row in rows]
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
    return {"status": "skipped", "job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_uuid = to_uuid(job_id)
    row = (
        await db.execute(
            text(
                "SELECT id, title, company, company_logo, location, type, min_salary, max_salary, "
                "salary_currency, salary_text, employment_mode, description, experience_level, "
                "posted_at, source, is_active, match_data FROM jobs WHERE id = :id"
            ),
            {"id": db_uuid},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    result = dict(row)
    result["id"] = job_id
    match_data = _parse_match_data(result.pop("match_data", None))
    result["source_url"] = match_data.get("source_url")
    result["skills"] = match_data.get("skills") or []
    result["company_logo"] = _proxied_company_logo_url(result.get("company_logo"), result.get("company"))
    return result


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
        db_job_uuid = to_uuid(job_id)
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
# Learning Path
# ════════════════════════════════════════════════════════════════

@app.post("/api/learning-path")
async def learning_path(
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = str(user["id"])
    skills = (
        await db.execute(
            text("SELECT skill FROM user_skills WHERE user_id = :uid"),
            {"uid": uid},
        )
    ).mappings().all()
    user_skills = {s["skill"] for s in skills}

    target_role = await _resolve_target_role(db, user)
    dqn_url = os.getenv("DQN_URL", os.getenv("DQN_SERVICE_URL", "http://dqn:8004")).rstrip("/")
    try:
        dqn_resp = await _client().post(
            f"{dqn_url}/learning-path",
            json={"user_id": uid, "current_skills": list(user_skills), "target_role": target_role},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        dqn_resp.raise_for_status()
        dqn_data = dqn_resp.json()
        steps = dqn_data.get("steps", [])
    except httpx.HTTPError:
        steps = []

    if not steps:
        fallback = [
            {"skill": "Python", "priority": 1, "estimated_weeks": 4, "resources": ["Coursera Python for Everybody", "Real Python Tutorials"]},
            {"skill": "SQL", "priority": 2, "estimated_weeks": 3, "resources": ["Mode SQL Tutorial", "SQLZoo"]},
            {"skill": "FastAPI", "priority": 3, "estimated_weeks": 3, "resources": ["FastAPI Documentation", "TestDriven.io FastAPI Course"]},
            {"skill": "Docker", "priority": 4, "estimated_weeks": 3, "resources": ["Docker Getting Started", "Play with Docker"]},
            {"skill": "Kubernetes", "priority": 5, "estimated_weeks": 6, "resources": ["Kubernetes Basics", "Kodekloud CKA Course"]},
            {"skill": "Machine Learning", "priority": 6, "estimated_weeks": 8, "resources": ["Andrew Ng ML Course", "Fast.ai Practical Deep Learning"]},
            {"skill": "TensorFlow", "priority": 7, "estimated_weeks": 5, "resources": ["TensorFlow Tutorials", "DeepLearning.AI TensorFlow Course"]},
        ]
        steps = [s for s in fallback if s["skill"] not in user_skills]
        if not steps:
            steps = fallback[:3]

    return {"steps": steps, "estimated_months": sum(s["estimated_weeks"] for s in steps) // 4}


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
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = str(request.user_id or user["id"])

    payload = request.model_dump()
    payload["user_id"] = uid
    payload["profile"] = request.profile or await _pipeline_profile_for_user(db, user)
    profile_for_reasons = payload["profile"] if isinstance(payload["profile"], dict) else {}
    payload["interaction_count"] = (
        request.interaction_count
        if request.interaction_count > 0
        else await _interaction_count_for_user(db, user["id"])
    )

    try:
        pipeline_resp = await _pipeline_post("/pipeline/run", payload)
    except HTTPException as exc:
        if exc.status_code in (502, 503, 504):
            return {
                "recommendations": [],
                "fairness_tpr_gap": 0.0,
                "degraded": True,
                "source_status": "pipeline_unavailable",
            }
        raise

    ranked = pipeline_resp.get("ranked", [])
    await _upsert_jobs_to_db(db, ranked)

    recommendations = []
    slate_id = str(uuid.uuid4())
    pipeline_run_id = str(pipeline_resp.get("run_id") or slate_id)
    for item in ranked:
        job = _map_pipeline_job(item)
        sbert_score = float(item.get("sbert_score") or 0.0)
        ncf_score = float(item.get("ncf_score") or 0.0)
        dqn_score = float(item.get("dqn_score") or 0.0)
        raw_explanation = item.get("explanation")
        if isinstance(raw_explanation, list):
            explanation = " ".join(str(part) for part in raw_explanation if str(part).strip())
        else:
            explanation = raw_explanation or (
                "Matched using SBERT semantic signal, NCF interaction signal, "
                "and DQN career-action signal."
            )
        weights = item.get("weights", {}) if isinstance(item.get("weights"), dict) else {}
        employer_fit = _employer_fit_score(user, job)
        recommendations.append({
            "job": job,
            "hybrid_score": item.get("final_score") or 0.0,
            "sbert_score": sbert_score,
            "ncf_score": ncf_score,
            "dqn_score": dqn_score,
            "weights": weights,
            "segment": item.get("segment"),
            "strategy": item.get("strategy") or pipeline_resp.get("stages", {}).get("aggregate", {}).get("strategy"),
            "recommendation_id": slate_id,
            "run_id": pipeline_run_id,
            "match_percent": item.get("match_percent") or 0,
            "explanation": explanation,
            "explanation_provenance": {
                "semantic_match": sbert_score,
                "behavior_match": ncf_score,
                "skill_path_signal": dqn_score,
                "skill_gap": item.get("skill_gap") or item.get("missing_skills") or [],
            },
            "reason_filter_scores": _recommendation_reason_filter_scores(
                profile_for_reasons,
                item,
                job,
                sbert_score=sbert_score,
                ncf_score=ncf_score,
                dqn_score=dqn_score,
            ),
            "reason_filter_labels": dict(REASON_FILTER_LABELS),
            "employer_fit": employer_fit,
        })

    fairness_tpr_gap = 0.0
    return {
        "recommendations": recommendations,
        "fairness_tpr_gap": fairness_tpr_gap,
        "recommendation_id": slate_id,
        "run_id": pipeline_run_id,
        "degraded": False,
    }


@app.post("/api/recommendations/feedback")
async def recommendation_feedback(
    body: RecommendationFeedbackRequest,
    token_payload: dict[str, Any] = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await _require_user(db, token_payload)
    uid = str(user["id"])

    job_uuid = to_uuid(body.job_id)
    slate_uuid = _coerce_uuid(body.served_slate_id or body.recommendation_id)
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
                "saved = user_job_interactions.saved OR EXCLUDED.saved, "
                "applied = user_job_interactions.applied OR EXCLUDED.applied, "
                "dismissed = user_job_interactions.dismissed OR EXCLUDED.dismissed, "
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
