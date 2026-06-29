"""Stage 1: fetch or reuse job candidates from the scraper service."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import uuid
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from sqlalchemy import Text as SqlText
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from services.shared.job_text import canonical_dict_from_row, canonical_job_text_hash
from services.shared.model_bundle import embedding_model_versions


JOB_CACHE: list[dict[str, Any]] = []
logger = logging.getLogger("scpa.pipeline.stage_1")
_db_engine: AsyncEngine | None = None
SCRAPER_RUN_TIMEOUT_SECONDS = float(os.getenv("SCRAPER_RUN_TIMEOUT_SECONDS", "120"))
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "trk",
}


def _async_db_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _database_url() -> str | None:
    return _async_db_url(
        os.getenv("PIPELINE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("GATEWAY_DATABASE_URL")
    )


def _get_db_engine() -> AsyncEngine | None:
    global _db_engine
    if os.getenv("PIPELINE_USE_DB_CANDIDATES", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    url = _database_url()
    if not url:
        return None
    if _db_engine is None:
        _db_engine = create_async_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=3)
    return _db_engine


def _stable_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(value))


def _normalize_source_url(value: Any) -> str:
    """Return a stable posting URL for cross-cycle deduplication."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")
    query_pairs = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_KEYS
    ]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip("/") or parsed.path,
        params="",
        query=urlencode(query_pairs, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def _job_identity_key(job: dict[str, Any]) -> str:
    """Prefer source URL identity so repeated continuous cycles hit one DB row."""
    source_url = _normalize_source_url(job.get("source_url"))
    if source_url:
        return f"source_url:{source_url}"
    source = _clean_source(job.get("source")) or "unknown"
    external_id = str(job.get("external_id") or job.get("job_id") or job.get("id") or "").strip()
    if external_id:
        return f"{source}:external:{external_id}"
    return "|".join(
        [
            source,
            str(job.get("title") or "").strip().lower(),
            str(job.get("company") or "").strip().lower(),
            str(job.get("location") or "").strip().lower(),
        ]
    )


def _payload_content_hash(job: dict[str, Any]) -> str:
    """Hash mutable job content separately from stable identity."""
    payload = {
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "location": job.get("location") or "",
        "description": job.get("description_text") or job.get("description") or "",
        "required_skills": job.get("required_skills") or job.get("required_skill_names") or [],
        "preferred_skills": job.get("preferred_skills") or job.get("preferred_skill_names") or [],
        "extracted_skills": job.get("extracted_skills") or job.get("extracted_skill_names") or [],
        "source_url": _normalize_source_url(job.get("source_url")),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def _clean_source(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.lower().strip().replace(" ", "").replace("-", "")
    allowed = {
        "jobstreet",
        "linkedin",
        "glints",
        "kalibrr",
        "karir",
        "topkarir",
        "kitalulus",
        "techinasia",
        "remotive",
        "indeed",
    }
    return cleaned if cleaned in allowed else None


@dataclass
class ScrapeStageResult:
    user: dict[str, Any]
    jobs: list[dict[str, Any]]
    summary: dict[str, Any]


def _build_user(user_id: str, profile: dict[str, Any] | None, interaction_count: int) -> dict[str, Any]:
    profile = profile or {}
    skills = profile.get("skills") or profile.get("keahlian") or ["Bahasa Inggris", "Public Speaking"]
    program_studi = profile.get("program_studi") or profile.get("jurusan") or "Sastra Inggris"
    jurusan = profile.get("jurusan") or program_studi
    interests = list(profile.get("interests") or [])
    # Interests join skills in the SBERT profile text so that the semantic
    # match reflects what the user cares about, not just what they can do.
    interest_text = " ".join(map(str, interests))
    profile_text = f"{program_studi} {jurusan} {' '.join(map(str, skills))} {interest_text}".strip()
    return {
        "id": str(user_id),
        "name": profile.get("name") or profile.get("nama") or "Ibnu",
        "program_studi": program_studi,
        "jurusan": jurusan,
        "university": profile.get("university") or profile.get("universitas") or "Universitas Negeri Surabaya",
        "skills": list(skills),
        "interests": interests,
        "location": profile.get("location"),
        "education_level": profile.get("education_level"),
        "interaction_count": interaction_count,
        "session_history": profile.get("session_history") or profile.get("interaction_history") or [],
        "profile_text": profile_text,
    }


def _normalize_scraped_jobs(raw_jobs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_jobs[:limit]):
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        job_id = str(raw.get("job_id") or raw.get("id") or raw.get("content_hash") or f"scraped-{index}")
        jobs.append(
            {
                "id": job_id,
                "job_id": job_id,
                "title": title,
                "company": raw.get("company") or "",
                "company_logo": raw.get("company_logo"),
                "location": raw.get("location") or "",
                "description": raw.get("description") or "",
                "raw_description_html": raw.get("raw_description_html"),
                "description_text": raw.get("description_text") or raw.get("description") or "",
                "description_sections": raw.get("description_sections") or {},
                "responsibilities": raw.get("responsibilities") or [],
                "requirements": raw.get("requirements") or [],
                "nice_to_have": raw.get("nice_to_have") or [],
                "benefits": raw.get("benefits") or [],
                "seniority_level": raw.get("seniority_level"),
                "employment_type": raw.get("employment_type"),
                "job_function": raw.get("job_function"),
                "industry": raw.get("industry"),
                "education_level": raw.get("education_level"),
                "years_experience_min": raw.get("years_experience_min"),
                "years_experience_max": raw.get("years_experience_max"),
                "required_skills": raw.get("required_skills") or raw.get("required_skill_names") or [],
                "preferred_skills": raw.get("preferred_skills") or raw.get("preferred_skill_names") or [],
                "extracted_skills": raw.get("extracted_skills") or raw.get("extracted_skill_names") or [],
                "tags": raw.get("tags") or [],
                "skills": (
                    raw.get("required_skills")
                    or raw.get("required_skill_names")
                    or raw.get("extracted_skills")
                    or raw.get("extracted_skill_names")
                    or raw.get("skills")
                    or raw.get("tags")
                    or []
                ),
                "source_url": raw.get("source_url"),
                "source": raw.get("source"),
                "source_updated_at": raw.get("source_updated_at"),
                "salary_text": raw.get("salary_text"),
                "content_hash": raw.get("content_hash"),
            }
        )
    return jobs


def _quality_gate_summary(source_stats: list[dict[str, Any]]) -> dict[str, Any]:
    for item in source_stats:
        if item.get("source") == "quality_gate":
            return {
                "accepted": item.get("count", 0),
                "rejected": item.get("rejected", 0),
                "rejection_reasons": item.get("rejection_reasons", {}),
                "min_description_chars": item.get("min_description_chars"),
            }
    return {"accepted": 0, "rejected": 0, "rejection_reasons": {}}


async def _fetch_jobs(
    client: httpx.AsyncClient, scraper_url: str, limit: int, seed_offset: int = 0
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    try:
        response = await client.post(
            f"{scraper_url}/scrape/run",
            params={"limit": limit, "seed_offset": max(0, int(seed_offset or 0))},
            timeout=SCRAPER_RUN_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        jobs = _normalize_scraped_jobs(data.get("jobs", []), limit)
        source_stats = data.get("source_stats", [])
        source_stats = source_stats if isinstance(source_stats, list) else []
        meta = {
            "count": data.get("count", len(jobs)),
            "deduplicated": data.get("deduplicated", 0),
            "source_stats": source_stats,
            "quality_gate": _quality_gate_summary(source_stats),
        }
        if jobs:
            return jobs, "scraper_run", meta
        logger.warning("scraper returned no real jobs; continuing with empty candidate pool")
        return [], "scraper_empty", meta
    except httpx.HTTPError as exc:
        logger.warning("scraper unavailable; refusing sample job fallback: %s", exc)
        return [], "scraper_unavailable", {"count": 0, "error": str(exc)}


async def _load_db_jobs(limit: int, offset: int = 0) -> list[dict[str, Any]]:
    engine = _get_db_engine()
    if engine is None:
        return []
    rows: list[dict[str, Any]] = []
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id::text AS id, title, company, company_logo, location, type::text AS type, "
                    "min_salary, max_salary, salary_currency, salary_text, employment_mode::text AS employment_mode, "
                    "description, raw_description_html, description_text, description_sections, responsibilities, "
                    "requirements, nice_to_have, benefits, seniority_level, employment_type, job_function, industry, "
                    "education_level, years_experience_min, years_experience_max, required_skill_names, "
                    "preferred_skill_names, extracted_skill_names, source_url, source_updated_at, "
                    "experience_level::text AS experience_level, posted_at, source::text AS source, "
                    "is_active, match_data FROM jobs WHERE is_active = true ORDER BY posted_at DESC LIMIT :limit OFFSET :offset"
                ),
                {"limit": limit, "offset": offset},
            )
            rows = [dict(row) for row in result.mappings().all()]
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("database candidate load failed: %s", exc)
        return []

    jobs: list[dict[str, Any]] = []
    for row in rows:
        match_data = _parse_match_data(row.pop("match_data", None))
        job_id = str(match_data.get("original_job_id") or row.get("id"))
        posted_at = row.get("posted_at")
        if posted_at is not None:
            row["posted_at"] = posted_at.isoformat() if hasattr(posted_at, "isoformat") else str(posted_at)
        cached_embedding = match_data.get("embedding")
        if not isinstance(cached_embedding, list):
            cached_embedding = []
        else:
            import math
            try:
                valid = True
                expected_dim = match_data.get("embedding_dimension")
                if expected_dim is not None and len(cached_embedding) != expected_dim:
                    valid = False
                if valid:
                    for val in cached_embedding:
                        if not isinstance(val, (int, float)) or math.isnan(float(val)) or math.isinf(float(val)):
                            valid = False
                            break
                if not valid:
                    cached_embedding = []
            except Exception:
                cached_embedding = []

        jobs.append(
            {
                **row,
                "id": str(row.get("id")),
                "job_id": job_id,
                "source_url": match_data.get("source_url") or row.get("source_url"),
                "skills": row.get("required_skill_names") or row.get("extracted_skill_names") or match_data.get("skills") or match_data.get("tags") or [],
                "tags": match_data.get("tags") or match_data.get("skills") or [],
                "salary_text": row.get("salary_text"),
                # SBERT job-embedding cache: reuse persisted vectors so /encode only
                # has to embed the user profile plus genuinely new/changed jobs.
                "embedding": cached_embedding,
                "embedding_text_hash": str(match_data.get("embedding_text_hash") or ""),
                "embedding_model_id": match_data.get("embedding_model_id"),
                "embedding_model_revision": match_data.get("embedding_model_revision"),
                "embedding_dimension": match_data.get("embedding_dimension"),
                "embedded_at": match_data.get("embedded_at"),
            }
        )
    return jobs


async def persist_job_embeddings(jobs: list[dict[str, Any]]) -> int:
    """Persist freshly computed SBERT job embeddings into jobs.match_data.

    Uses a jsonb merge (``match_data || ...``) so unrelated keys survive.
    Returns the number of rows updated. Failures are logged, never raised:
    the recommendation slate is already computed at this point and a cache
    write must not break the response.
    """
    engine = _get_db_engine()
    if engine is None:
        return 0
    params: list[dict[str, Any]] = []
    for job in jobs:
        embedding = job.get("embedding")
        text_hash = str(job.get("embedding_text_hash") or "")
        row_id = str(job.get("id") or "")
        if not row_id or not text_hash or not isinstance(embedding, list) or not embedding:
            continue
        try:
            row_uuid = uuid.UUID(row_id)
        except ValueError:
            continue
        params.append(
            {
                "id": row_uuid,
                "embedding_patch": json.dumps(
                    {
                        "embedding": [float(value) for value in embedding],
                        "embedding_text_hash": text_hash,
                        "embedding_model_id": job.get("embedding_model_id"),
                        "embedding_model_revision": job.get("embedding_model_revision"),
                        "embedding_dimension": job.get("embedding_dimension"),
                        "embedded_at": job.get("embedded_at"),
                    }
                ),
            }
        )
    if not params:
        return 0
    try:
        persisted = 0
        async with engine.begin() as conn:
            # Row-by-row execution: asyncpg's executemany reports rowcount=-1
            # per batch, which previously produced negative "persisted" totals.
            for param in params:
                result = await conn.execute(
                    text(
                        "UPDATE jobs SET match_data = COALESCE(match_data, '{}'::jsonb) || "
                        "CAST(:embedding_patch AS jsonb) WHERE id = :id"
                    ),
                    param,
                )
                persisted += max(int(result.rowcount or 0), 0)
        return persisted
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("job embedding persistence failed: %s", exc)
        return 0


# Transactional outbox (contract §8): a committed job upsert must never exist
# without a recoverable embedding task. Executed inside the same transaction as
# the job upsert. Skips task creation when an up-to-date ready embedding already
# exists (unchanged rescrape => no re-embed). New job => priority 100, changed
# semantic content => 90; the stale embedding row is demoted in the same tx so
# online retrieval never serves a vector for outdated content.
_OUTBOX_MARK_STALE_SQL = text(
    "UPDATE job_embeddings SET status = 'stale', updated_at = NOW() "
    "WHERE job_id = :id AND model_version = :model_version "
    "AND content_hash <> :embedding_content_hash AND status = 'ready'"
)
_OUTBOX_INSERT_TASK_SQL = text(
    "INSERT INTO embedding_tasks (job_id, model_version, content_hash, status, priority) "
    "SELECT CAST(:id AS uuid), CAST(:model_version AS varchar), "
    "  CAST(:embedding_content_hash AS varchar), 'pending', "
    "  CASE WHEN EXISTS ("
    "    SELECT 1 FROM job_embeddings je WHERE je.job_id = :id AND je.model_version = :model_version"
    "  ) THEN 90 ELSE 100 END "
    "WHERE NOT EXISTS ("
    "  SELECT 1 FROM job_embeddings je2 WHERE je2.job_id = :id "
    "    AND je2.model_version = :model_version "
    "    AND je2.content_hash = :embedding_content_hash AND je2.status = 'ready'"
    ") "
    "ON CONFLICT (job_id, model_version, content_hash) DO NOTHING"
)


# Post-commit wake signal for the embedding worker. Redis is transport only:
# pushed AFTER the outbox transaction commits, and failures merely leave the
# worker on its poll interval (PostgreSQL remains the source of truth).
_WAKE_LIST_KEY = "scpa:embed:wake"
_wake_redis: Any = None


async def _signal_embedding_worker(queued: int) -> None:
    global _wake_redis
    if queued <= 0:
        return
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return
    try:
        if _wake_redis is None:
            import redis.asyncio as aioredis

            _wake_redis = aioredis.from_url(
                redis_url, decode_responses=True, socket_connect_timeout=2
            )
        await _wake_redis.lpush(_WAKE_LIST_KEY, str(queued))
        await _wake_redis.ltrim(_WAKE_LIST_KEY, 0, 99)
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("embedding worker wake signal failed: %s", exc)


# Catalog repost suppression (DATA-DEDUP-CATALOG-001): job boards repost the
# same vacancy under new URLs, and source_url identity rightly stores each
# repost. Within the upsert transaction we keep only the newest active row
# per (title, company, location) fingerprint among rows sharing a fingerprint
# with this batch — so a rescrape can never resurrect an older copy, and the
# catalog converges instead of accumulating thousands of duplicates.
# Deactivated rows keep their data and stay resolvable by id (saved/applied
# references); only listing/retrieval eligibility is removed.
_CATALOG_DEDUP_SWEEP_SQL = text(
    """
    WITH batch_fp AS (
        SELECT DISTINCT lower(trim(title)) AS t, lower(trim(company)) AS c,
               lower(coalesce(trim(location), '')) AS l
        FROM jobs WHERE id = ANY(CAST(:ids AS uuid[]))
    ),
    ranked AS (
        SELECT j.id, row_number() OVER (
            PARTITION BY lower(trim(j.title)), lower(trim(j.company)),
                         lower(coalesce(trim(j.location), ''))
            ORDER BY j.posted_at DESC NULLS LAST,
                     j.last_seen_at DESC NULLS LAST, j.id
        ) AS rn
        FROM jobs j
        JOIN batch_fp b
          ON lower(trim(j.title)) = b.t
         AND lower(trim(j.company)) = b.c
         AND lower(coalesce(trim(j.location), '')) = b.l
        WHERE j.is_active AND j.quality_status = 'accepted'
    )
    UPDATE jobs SET is_active = false,
        match_data = coalesce(jobs.match_data, '{}'::jsonb)
            || jsonb_build_object('catalog_dedup_deactivated_at', NOW()::text)
    FROM ranked WHERE jobs.id = ranked.id AND ranked.rn > 1
    """
)


async def _suppress_repost_duplicates(conn: Any, job_ids: list[Any]) -> int:
    if not job_ids:
        return 0
    result = await conn.execute(
        _CATALOG_DEDUP_SWEEP_SQL, {"ids": [str(job_id) for job_id in job_ids]}
    )
    return max(int(result.rowcount or 0), 0)


async def _enqueue_embedding_tasks(conn: Any, params: list[dict[str, Any]]) -> int:
    """Create outbox tasks for upserted jobs inside the caller's transaction."""
    queued = 0
    for model_version in embedding_model_versions():
        for param in params:
            task_param = {
                "id": param["id"],
                "model_version": model_version,
                "embedding_content_hash": param["embedding_content_hash"],
            }
            await conn.execute(_OUTBOX_MARK_STALE_SQL, task_param)
            result = await conn.execute(_OUTBOX_INSERT_TASK_SQL, task_param)
            queued += max(int(result.rowcount or 0), 0)
    return queued


async def _upsert_scraped_jobs(jobs: list[dict[str, Any]]) -> int:
    engine = _get_db_engine()
    if engine is None or not jobs:
        return 0
    params: list[dict[str, Any]] = []
    for job in jobs:
        title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip() or "Unknown Company"
        if not title:
            continue
        identity_key = _job_identity_key(job)
        original_id = str(job.get("job_id") or job.get("id") or job.get("content_hash") or title)
        normalized_source_url = _normalize_source_url(job.get("source_url"))
        skills = job.get("skills") or job.get("tags") or []
        if not isinstance(skills, list):
            skills = [str(skills)]
        required_skills = job.get("required_skills") or job.get("required_skill_names") or []
        preferred_skills = job.get("preferred_skills") or job.get("preferred_skill_names") or []
        extracted_skills = job.get("extracted_skills") or job.get("extracted_skill_names") or []
        params.append(
            {
                "id": _stable_uuid(identity_key),
                "external_id": original_id,
                "title": title,
                "company": company,
                "company_logo": job.get("company_logo"),
                "location": job.get("location") or None,
                "description": job.get("description") or None,
                "raw_description_html": job.get("raw_description_html") or None,
                "description_text": job.get("description_text") or job.get("description") or None,
                "description_sections": json.dumps(job.get("description_sections") or {}),
                "responsibilities": job.get("responsibilities") or [],
                "requirements": job.get("requirements") or [],
                "nice_to_have": job.get("nice_to_have") or [],
                "benefits": job.get("benefits") or [],
                "seniority_level": job.get("seniority_level") or None,
                "employment_type": job.get("employment_type") or None,
                "job_function": job.get("job_function") or None,
                "industry": job.get("industry") or None,
                "education_level": job.get("education_level") or None,
                "years_experience_min": job.get("years_experience_min"),
                "years_experience_max": job.get("years_experience_max"),
                "required_skill_names": required_skills,
                "preferred_skill_names": preferred_skills,
                "extracted_skill_names": extracted_skills,
                "source_url": normalized_source_url or job.get("source_url"),
                "source_updated_at": job.get("source_updated_at"),
                "salary_text": job.get("salary_text") or None,
                "source": _clean_source(job.get("source")),
                "is_active": bool(job.get("is_active", True)),
                "quality_status": "accepted",
                "quality_reject_reason": None,
                "content_hash": job.get("content_hash") or _payload_content_hash(job),
                "match_data": json.dumps(
                    {
                        "original_job_id": original_id,
                        "identity_key": identity_key,
                        "source_url": normalized_source_url or job.get("source_url"),
                        "skills": required_skills or extracted_skills,
                        "tags": job.get("tags") or skills,
                        "required_skills": required_skills,
                        "preferred_skills": preferred_skills,
                        "extracted_skills": extracted_skills,
                    }
                ),
            }
        )
    if not params:
        return 0
    try:
        async with engine.begin() as conn:
            upsert_stmt = text(
                "INSERT INTO jobs ("
                "id, title, company, company_logo, location, description, raw_description_html, description_text, "
                "description_sections, responsibilities, requirements, nice_to_have, benefits, seniority_level, "
                "employment_type, job_function, industry, education_level, years_experience_min, years_experience_max, "
                "required_skill_names, preferred_skill_names, extracted_skill_names, source_url, source_updated_at, "
                "salary_text, source, is_active, external_id, scraped_at, first_seen_at, last_seen_at, "
                "quality_status, quality_reject_reason, content_hash, match_data"
                ") VALUES ("
                ":id, :title, :company, :company_logo, :location, :description, :raw_description_html, :description_text, "
                "CAST(:description_sections AS jsonb), :responsibilities, :requirements, :nice_to_have, :benefits, :seniority_level, "
                ":employment_type, :job_function, :industry, :education_level, :years_experience_min, :years_experience_max, "
                ":required_skill_names, :preferred_skill_names, :extracted_skill_names, :source_url, :source_updated_at, "
                ":salary_text, :source, :is_active, :external_id, NOW(), NOW(), NOW(), "
                ":quality_status, :quality_reject_reason, :content_hash, CAST(:match_data AS jsonb)"
                ") "
                "ON CONFLICT (source_url) WHERE source_url IS NOT NULL AND source_url <> '' DO UPDATE SET "
                "title = EXCLUDED.title, company = EXCLUDED.company, company_logo = EXCLUDED.company_logo, "
                "location = EXCLUDED.location, description = EXCLUDED.description, raw_description_html = EXCLUDED.raw_description_html, "
                "description_text = EXCLUDED.description_text, description_sections = EXCLUDED.description_sections, "
                "responsibilities = EXCLUDED.responsibilities, requirements = EXCLUDED.requirements, nice_to_have = EXCLUDED.nice_to_have, "
                "benefits = EXCLUDED.benefits, seniority_level = EXCLUDED.seniority_level, employment_type = EXCLUDED.employment_type, "
                "job_function = EXCLUDED.job_function, industry = EXCLUDED.industry, education_level = EXCLUDED.education_level, "
                "years_experience_min = EXCLUDED.years_experience_min, years_experience_max = EXCLUDED.years_experience_max, "
                "required_skill_names = EXCLUDED.required_skill_names, preferred_skill_names = EXCLUDED.preferred_skill_names, "
                "extracted_skill_names = EXCLUDED.extracted_skill_names, source_url = EXCLUDED.source_url, source_updated_at = EXCLUDED.source_updated_at, "
                "salary_text = EXCLUDED.salary_text, source = EXCLUDED.source, is_active = EXCLUDED.is_active, "
                "external_id = COALESCE(EXCLUDED.external_id, jobs.external_id), scraped_at = EXCLUDED.scraped_at, "
                "first_seen_at = COALESCE(jobs.first_seen_at, EXCLUDED.first_seen_at), last_seen_at = EXCLUDED.last_seen_at, "
                "quality_status = EXCLUDED.quality_status, quality_reject_reason = EXCLUDED.quality_reject_reason, "
                "content_hash = EXCLUDED.content_hash, "
                "match_data = COALESCE(jobs.match_data, '{}'::jsonb) || EXCLUDED.match_data "
                # single-producer hash contract: the outbox hashes the
                # POST-WRITE row through the same shared mapping the worker
                # and reconciler use, so scraped-dict vs DB-row shape
                # differences can never disagree again.
                "RETURNING id, title, company, location, job_function, industry, "
                "seniority_level, employment_type, experience_level::text AS experience_level, "
                "description_text, description, description_sections, responsibilities, "
                "requirements, nice_to_have, required_skill_names, preferred_skill_names, "
                "extracted_skill_names, match_data"
            ).bindparams(
                bindparam("responsibilities", type_=ARRAY(SqlText())),
                bindparam("requirements", type_=ARRAY(SqlText())),
                bindparam("nice_to_have", type_=ARRAY(SqlText())),
                bindparam("benefits", type_=ARRAY(SqlText())),
                bindparam("required_skill_names", type_=ARRAY(SqlText())),
                bindparam("preferred_skill_names", type_=ARRAY(SqlText())),
                bindparam("extracted_skill_names", type_=ARRAY(SqlText())),
            )
            # Per-row execution with RETURNING: the ON CONFLICT (source_url)
            # path can land on an existing row whose id differs from the
            # identity-derived uuid, and the outbox task must reference the
            # actual row id or its FK would abort the whole transaction.
            outbox_params: list[dict[str, Any]] = []
            for param in params:
                result = await conn.execute(upsert_stmt, param)
                row = result.mappings().first()
                if row is None:
                    continue
                row_dict = dict(row)
                outbox_params.append(
                    {
                        "id": row_dict["id"],
                        "embedding_content_hash": canonical_job_text_hash(
                            canonical_dict_from_row(row_dict)
                        ),
                    }
                )
            queued = await _enqueue_embedding_tasks(conn, outbox_params)
            if queued:
                logger.info(
                    "embedding outbox queued tasks=%s for upserted jobs=%s",
                    queued,
                    len(outbox_params),
                )
            suppressed = await _suppress_repost_duplicates(
                conn, [item["id"] for item in outbox_params]
            )
            if suppressed:
                logger.info("catalog dedup deactivated reposts=%s", suppressed)
        # Outside the transaction: signal only after the tasks are durable.
        await _signal_embedding_worker(queued)
        return len(params)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("database scraped-job upsert failed: %s", exc)
        return 0


def _merge_jobs(primary: list[dict[str, Any]], secondary: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str] | str] = set()
    for job in [*primary, *secondary]:
        source_url = str(job.get("source_url") or "").strip().lower()
        fingerprint: tuple[str, str, str] | str = source_url or (
            str(job.get("title") or "").strip().lower(),
            str(job.get("company") or "").strip().lower(),
            str(job.get("location") or "").strip().lower(),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged.append(job)
        if len(merged) >= limit:
            break
    return merged


async def run_scrape_stage(
    client: httpx.AsyncClient,
    scraper_url: str,
    user_id: str,
    profile: dict[str, Any] | None,
    interaction_count: int,
    refresh_jobs: bool,
    limit: int,
    seed_offset: int = 0,
) -> ScrapeStageResult:
    user = _build_user(user_id, profile, interaction_count)
    skipped = bool(JOB_CACHE) and not refresh_jobs

    db_jobs = await _load_db_jobs(limit)
    scraped_jobs: list[dict[str, Any]] = []
    scrape_meta: dict[str, Any] = {}
    upserted = 0

    if db_jobs and not refresh_jobs:
        jobs = db_jobs
        source = "database"
    elif skipped and not db_jobs:
        jobs = JOB_CACHE[:limit]
        source = "cache"
    else:
        scraped_jobs, source, scrape_meta = await _fetch_jobs(
            client,
            scraper_url.rstrip("/"),
            limit,
            seed_offset=seed_offset,
        )
        upserted = await _upsert_scraped_jobs(scraped_jobs)
        refreshed_db_jobs = await _load_db_jobs(limit)
        jobs = _merge_jobs(refreshed_db_jobs, scraped_jobs, limit)
        source = f"{source}+database" if refreshed_db_jobs else source
        if upserted:
            source = f"{source}:upserted={upserted}"
        JOB_CACHE[:] = jobs

    return ScrapeStageResult(
        user=user,
        jobs=jobs[:limit],
        summary={
            "skipped_scrape": skipped,
            "refresh_requested": refresh_jobs,
            "source": source,
            "cached_jobs": len(JOB_CACHE),
            "database_jobs": len(db_jobs),
            "scraped_jobs": len(scraped_jobs),
            "upserted_jobs": upserted,
            "returned_jobs": len(jobs[:limit]),
            "scraper": scrape_meta,
        },
    )
