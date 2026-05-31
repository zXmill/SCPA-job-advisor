"""SCPA Database Models — SQLAlchemy 2.x ORM

Defines all 5 core tables and 8 PostgreSQL ENUM types for the
Smart Career Pathway Assistant platform.

Tables:
    - users: User profiles and authentication credentials
    - jobs: Job vacancy listings with ML metadata
    - applications: User ↔ Job application records
    - user_skills: User skill catalog with proficiency levels
    - user_interactions: DQN training data (click/view/apply logs)
    - skills: Controlled skill vocabulary learned from scraped jobs
    - job_required_skills: Job-to-skill requirements
    - certification_skills: Certificate-to-skill mapping rules
    - user_certifications: OCR-derived user certificate records
    - skill_gap_snapshots: Historical skill-gap output shown to a user

ENUMs:
    - UserRole, JobType, EmploymentMode, ExperienceLevel
    - JobSource, ApplicationStatus, SkillCategory, ProficiencyLevel

Usage:
    from db.models import Base, User, Job, Application, UserSkill, UserInteraction, Skill
    from db.models import get_async_engine, get_async_session_factory
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

import logging
import os

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# PostgreSQL ENUM Types
# ════════════════════════════════════════════════════════════════

class UserRole(str, enum.Enum):
    """User account role levels."""

    USER = "user"
    ADMIN = "admin"
    PREMIUM = "premium"


class JobType(str, enum.Enum):
    """Employment contract types."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class EmploymentMode(str, enum.Enum):
    """Work location arrangement."""

    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class ExperienceLevel(str, enum.Enum):
    """Required experience seniority."""

    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"


class JobSource(str, enum.Enum):
    """External job board source identifier.

    Includes Indonesian local portals (Kalibrr, Karir, TopKarir,
    KitaLulus, Tech in Asia) and global aggregators (Remotive, Indeed)
    added in migration 002_extend_jobsource_enum.
    """

    JOBSTREET = "jobstreet"
    LINKEDIN = "linkedin"
    GLINTS = "glints"
    KALIBRR = "kalibrr"
    KARIR = "karir"
    TOPKARIR = "topkarir"
    KITALULUS = "kitalulus"
    TECHINASIA = "techinasia"
    REMOTIVE = "remotive"
    INDEED = "indeed"


class ApplicationStatus(str, enum.Enum):
    """Application lifecycle states."""

    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class SkillCategory(str, enum.Enum):
    """Skill classification taxonomy."""

    TECHNICAL = "technical"
    SOFT = "soft"
    LINGUISTIC = "linguistic"


class ProficiencyLevel(str, enum.Enum):
    """Skill mastery level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# ════════════════════════════════════════════════════════════════
# Declarative Base
# ════════════════════════════════════════════════════════════════

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SCPA ORM models.

    Inherits ``AsyncAttrs`` to support lazy-loading in async contexts.
    """

    pass


# ════════════════════════════════════════════════════════════════
# ORM Models
# ════════════════════════════════════════════════════════════════

class User(Base):
    """User profile and authentication record.

    Attributes:
        id: UUID primary key (auto-generated).
        name: Full display name.
        email: Unique login email address.
        password_hash: Bcrypt/Argon2 hashed password.
        program_studi: Academic study program (nullable).
        university: University affiliation (nullable).
        completion_percent: Profile completeness 0-100.
        role: Account role (user/admin/premium).
        email_verified: Whether email has been confirmed.
        last_login_at: Timestamp of most recent login.
        created_at: Account creation timestamp.
        updated_at: Last profile modification timestamp.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    program_studi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    university: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    completion_percent: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", native_enum=True, create_constraint=False),
        server_default=text("'user'"),
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    cv_embedding: Mapped[Optional[List[float]]] = mapped_column(
        ARRAY(Float), nullable=True
    )
    cv_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relationships ──
    skills: Mapped[List["UserSkill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    applications: Mapped[List["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    interactions: Mapped[List["UserInteraction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    job_alerts: Mapped[List["JobAlert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    served_slates: Mapped[List["ServedSlate"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    feedback_events: Mapped[List["FeedbackEvent"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    dqn_episodes: Mapped[List["DQNEpisode"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    certifications: Mapped[List["UserCertification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    # ── Indexes (matching Index Strategy in README §1.6) ──
    __table_args__ = (
        Index("idx_users_email", "email", unique=True),
        Index("idx_users_completion", "completion_percent"),
        Index("idx_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, email={self.email!r}, role={self.role!r})>"


class Job(Base):
    """Job vacancy listing with ML metadata.

    Attributes:
        id: UUID primary key.
        title: Job title (max 500 chars).
        company: Employer company name.
        location: Work location (city/region).
        type: Contract type enum.
        min_salary: Minimum salary offer.
        max_salary: Maximum salary offer.
        salary_currency: ISO 4217 currency code (default IDR).
        employment_mode: Onsite/remote/hybrid.
        description: Full job description text.
        experience_level: Required seniority.
        posted_at: Original posting timestamp.
        source: External job board source.
        is_active: Whether the listing is still open.
        match_data: JSONB field for ML-computed metadata.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    company_logo: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[Optional[JobType]] = mapped_column(
        Enum(JobType, name="jobtype", native_enum=True, create_constraint=False),
        nullable=True,
    )
    min_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_salary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(
        String(3), server_default=text("'IDR'"), nullable=False
    )
    salary_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    employment_mode: Mapped[Optional[EmploymentMode]] = mapped_column(
        Enum(
            EmploymentMode,
            name="employmentmode",
            native_enum=True,
            create_constraint=False,
        ),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_description_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_sections: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    responsibilities: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    requirements: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    nice_to_have: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    benefits: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    seniority_level: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    job_function: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    education_level: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    years_experience_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_experience_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_skill_names: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    preferred_skill_names: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    extracted_skill_names: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    experience_level: Mapped[Optional[ExperienceLevel]] = mapped_column(
        Enum(
            ExperienceLevel,
            name="experiencelevel",
            native_enum=True,
            create_constraint=False,
        ),
        nullable=True,
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    source: Mapped[Optional[JobSource]] = mapped_column(
        Enum(JobSource, name="jobsource", native_enum=True, create_constraint=False),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    match_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    skills_extracted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # ── Relationships ──
    applications: Mapped[List["Application"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )
    served_slate_items: Mapped[List["ServedSlateItem"]] = relationship(
        back_populates="job", lazy="selectin"
    )
    feedback_events: Mapped[List["FeedbackEvent"]] = relationship(
        back_populates="job", lazy="selectin"
    )
    required_skills: Mapped[List["JobRequiredSkill"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )

    # ── Indexes ──
    __table_args__ = (
        Index("idx_jobs_company", "company"),
        Index("idx_jobs_location", "location"),
        Index("idx_jobs_source", "source"),
        Index("idx_jobs_source_url", "source_url"),
        Index("idx_jobs_posted_at", posted_at.desc()),
        Index(
            "idx_jobs_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_jobs_active_posted_id",
            posted_at.desc(),
            "id",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_jobs_active_source_posted",
            "source",
            posted_at.desc(),
            "id",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_jobs_active_experience_posted",
            "experience_level",
            posted_at.desc(),
            "id",
            postgresql_where=text("is_active = true"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id!r}, title={self.title!r}, company={self.company!r})>"


class Application(Base):
    """User ↔ Job application record with lifecycle status.

    Attributes:
        id: UUID primary key.
        user_id: FK to users.id.
        job_id: FK to jobs.id.
        status: Application lifecycle state enum.
        cover_letter: Optional cover letter text.
        resume_url: URL to uploaded resume file.
        applied_via: Application channel (web/mobile/api).
        applied_at: Submission timestamp.
        updated_at: Last status change timestamp.
    """

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="applicationstatus",
            native_enum=True,
            create_constraint=False,
        ),
        server_default=text("'submitted'"),
        nullable=False,
    )
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    applied_via: Mapped[str] = mapped_column(
        String(20), server_default=text("'web'"), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")

    # ── Indexes & Constraints ──
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job"),
        Index("idx_applications_status", "status"),
        Index("idx_applications_user", "user_id"),
        Index("idx_applications_job", "job_id"),
        Index("idx_applications_user_applied", "user_id", applied_at.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<Application(id={self.id!r}, user_id={self.user_id!r}, "
            f"job_id={self.job_id!r}, status={self.status!r})>"
        )


class UserSkill(Base):
    """User skill entry with category and proficiency level.

    Attributes:
        id: Auto-incrementing BigInteger primary key.
        user_id: FK to users.id.
        skill: Skill name (max 100 chars).
        category: Skill taxonomy (technical/soft/linguistic).
        proficiency_level: Mastery level.
        endorsed: Whether the skill has been endorsed/verified.
        created_at: Record creation timestamp.
    """

    __tablename__ = "user_skills"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[SkillCategory] = mapped_column(
        Enum(
            SkillCategory,
            name="skillcategory",
            native_enum=True,
            create_constraint=False,
        ),
        server_default=text("'technical'"),
        nullable=False,
    )
    proficiency_level: Mapped[ProficiencyLevel] = mapped_column(
        Enum(
            ProficiencyLevel,
            name="proficiencylevel",
            native_enum=True,
            create_constraint=False,
        ),
        server_default=text("'beginner'"),
        nullable=False,
    )
    endorsed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="skills")

    # ── Indexes ──
    __table_args__ = (
        Index("idx_user_skills_user", "user_id", "skill", unique=True),
        Index("idx_user_skills_skill", "skill"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSkill(id={self.id!r}, user_id={self.user_id!r}, "
            f"skill={self.skill!r}, level={self.proficiency_level!r})>"
        )


class Skill(Base):
    """Controlled skill vocabulary item used by profile input and job taxonomy."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(
        String(32), server_default=text("'technical'"), nullable=False
    )
    frequency: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    aliases: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(64), server_default=text("'local'"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(
        Float, server_default=text("1.0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    job_requirements: Mapped[List["JobRequiredSkill"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_skills_name", "name"),
        Index("idx_skills_category", "category"),
        Index("idx_skills_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id!r}, name={self.name!r}, category={self.category!r})>"


class JobRequiredSkill(Base):
    """Many-to-many join between jobs and controlled skill requirements."""

    __tablename__ = "job_required_skills"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    importance: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    job: Mapped["Job"] = relationship(back_populates="required_skills")
    skill: Mapped["Skill"] = relationship(back_populates="job_requirements")

    __table_args__ = (
        UniqueConstraint("job_id", "skill_id", name="uq_job_required_skills_job_skill"),
        Index("idx_jrs_job", "job_id"),
        Index("idx_jrs_skill", "skill_id"),
    )


class CertificationSkill(Base):
    """Mapping rule from certificate names or issuers to skills."""

    __tablename__ = "certification_skills"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cert_name_regex: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mapped_skills: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )


class UserCertification(Base):
    """Certificate OCR result uploaded by a user."""

    __tablename__ = "user_certifications"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    cert_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ocr_confidence: Mapped[str] = mapped_column(
        String(20), server_default=text("'medium'"), nullable=False
    )
    mapped_skills: Mapped[List[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), server_default=text("'confirmed'"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="certifications")

    __table_args__ = (
        Index("idx_uc_user", "user_id"),
    )


class UserInteraction(Base):
    """User interaction log for DQN training data.

    Records user actions (click, view, apply, save) on various
    target types (job, course, article) for reinforcement learning.

    Attributes:
        id: Auto-incrementing BigInteger primary key.
        user_id: FK to users.id.
        action_type: Action performed (click/view/apply/save/dismiss).
        target_type: Entity type of the target (job/course/article).
        target_id: UUID of the target entity (polymorphic, no FK).
        session_id: Browser/app session identifier.
        metadata: JSONB with additional context (duration, source, etc.).
        created_at: Interaction timestamp.
    """

    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    # ── Relationships ──
    user: Mapped["User"] = relationship(back_populates="interactions")

    # ── Indexes ──
    __table_args__ = (
        Index(
            "idx_interactions_user_time",
            "user_id",
            created_at.desc(),
        ),
        Index("idx_interactions_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserInteraction(id={self.id!r}, user_id={self.user_id!r}, "
            f"action={self.action_type!r}, target={self.target_type!r})>"
        )


class UserJobInteraction(Base):
    """Explicit user-job interaction matrix for NCF training."""

    __tablename__ = "user_job_interactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    clicked: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    saved: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    applied: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    dismissed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_user_job_interactions_user", "user_id", created_at.desc()),
        Index("idx_user_job_interactions_job", "job_id"),
        UniqueConstraint("user_id", "job_id", name="uq_user_job_interaction"),
    )


class JobAlert(Base):
    """Durable user job-alert preference."""

    __tablename__ = "job_alerts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    query: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    min_match_percent: Mapped[int] = mapped_column(
        Integer, server_default=text("60"), nullable=False
    )
    frequency: Mapped[str] = mapped_column(
        String(20), server_default=text("'daily'"), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="job_alerts")

    __table_args__ = (
        Index("idx_job_alerts_user_active", "user_id", "active"),
        Index("idx_job_alerts_user_created", "user_id", created_at.desc()),
        Index("idx_job_alerts_frequency_active", "frequency", "active"),
    )


class DQNSessionLog(Base):
    """Historical recommendation-session log for offline DQN bootstrap."""

    __tablename__ = "dqn_session_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_history: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    candidate_jobs: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    rewards: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_dqn_session_logs_session", "session_id"),
        Index("idx_dqn_session_logs_user_time", "user_id", created_at.desc()),
    )


class DQNReplayArchive(Base):
    """PostgreSQL archive copy of DQN replay experiences."""

    __tablename__ = "dqn_replay_archive"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[List[float]] = mapped_column(ARRAY(Float), nullable=False)
    action: Mapped[int] = mapped_column(Integer, nullable=False)
    reward: Mapped[float] = mapped_column(Float, nullable=False)
    next_state: Mapped[List[float]] = mapped_column(ARRAY(Float), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_dqn_replay_archive_created", "created_at"),
        Index("idx_dqn_replay_archive_user", "user_id"),
    )


class ServedSlate(Base):
    """Recommendation slate served to a user with model provenance."""

    __tablename__ = "served_slates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_versions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    fallback_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="served_slates")
    items: Mapped[List["ServedSlateItem"]] = relationship(
        back_populates="slate", cascade="all, delete-orphan", lazy="selectin"
    )
    feedback_events: Mapped[List["FeedbackEvent"]] = relationship(
        back_populates="slate", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_served_slates_user_time", "user_id", created_at.desc()),
        Index("idx_served_slates_pipeline_run", "pipeline_run_id"),
    )


class ServedSlateItem(Base):
    """Single ranked item inside a served recommendation slate."""

    __tablename__ = "served_slate_items"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    slate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("served_slates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    component_scores: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    model_versions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    fallback_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    explanation: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    slate: Mapped["ServedSlate"] = relationship(back_populates="items")
    job: Mapped[Optional["Job"]] = relationship(back_populates="served_slate_items")
    feedback_events: Mapped[List["FeedbackEvent"]] = relationship(
        back_populates="slate_item", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("slate_id", "rank", name="uq_served_slate_rank"),
        Index("idx_served_slate_items_slate_rank", "slate_id", "rank"),
        Index("idx_served_slate_items_job", "job_id"),
    )


class FeedbackEvent(Base):
    """Exposure-aware recommendation feedback event."""

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    slate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("served_slates.id", ondelete="SET NULL"),
        nullable=True,
    )
    slate_item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("served_slate_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dwell_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    fallback_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="feedback_events")
    job: Mapped[Optional["Job"]] = relationship(back_populates="feedback_events")
    slate: Mapped[Optional["ServedSlate"]] = relationship(
        back_populates="feedback_events"
    )
    slate_item: Mapped[Optional["ServedSlateItem"]] = relationship(
        back_populates="feedback_events"
    )

    __table_args__ = (
        Index("idx_feedback_events_user_time", "user_id", created_at.desc()),
        Index("idx_feedback_events_slate_rank", "slate_id", "rank"),
        Index("idx_feedback_events_type_time", "event_type", created_at.desc()),
        Index("idx_feedback_events_job_time", "job_id", created_at.desc()),
    )


class ModelFeedbackOutbox(Base):
    """Durable delivery queue for model feedback forwarding."""

    __tablename__ = "model_feedback_outbox"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), server_default=text("'pending'"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_model_feedback_outbox_status_next",
            "status",
            "next_attempt_at",
        ),
        Index("idx_model_feedback_outbox_user_time", "user_id", created_at.desc()),
        Index("idx_model_feedback_outbox_job_time", "job_id", created_at.desc()),
    )


class ModelArtifact(Base):
    """Persisted model artifact lineage for SBERT, NCF, DQN, and Hybrid."""

    __tablename__ = "model_artifacts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    training_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    fallback_mode: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "service",
            "model_version",
            "artifact_path",
            name="uq_model_artifact_version_path",
        ),
        Index("idx_model_artifacts_service_version", "service", "model_version"),
        Index(
            "idx_model_artifacts_active",
            "service",
            "active",
            postgresql_where=text("active = true"),
        ),
        Index("idx_model_artifacts_created", "created_at"),
    )


class EmbeddingCacheEntry(Base):
    """Database-backed SBERT embedding cache row with model provenance."""

    __tablename__ = "embedding_cache_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    source_text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[List[float]] = mapped_column(ARRAY(Float), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    service: Mapped[str] = mapped_column(
        String(32), server_default=text("'sbert'"), nullable=False
    )
    fallback_mode: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_embedding_cache_model_version", "model_version"),
        Index("idx_embedding_cache_text_hash", "source_text_hash"),
        Index("idx_embedding_cache_expires", "expires_at"),
    )


class ModelEntityMapping(Base):
    """Stable external-to-internal model ID mapping for recommender services."""

    __tablename__ = "model_entity_mappings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_uuid: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    internal_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "service",
            "model_version",
            "entity_type",
            "external_id",
            name="uq_model_entity_external",
        ),
        UniqueConstraint(
            "service",
            "model_version",
            "entity_type",
            "internal_index",
            name="uq_model_entity_internal_index",
        ),
        Index(
            "idx_model_entity_mapping_lookup",
            "service",
            "model_version",
            "entity_type",
        ),
    )


class DQNEpisode(Base):
    """Persisted DQN MDP transition with policy provenance."""

    __tablename__ = "dqn_episodes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    slate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("served_slates.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    reward: Mapped[float] = mapped_column(Float, nullable=False)
    next_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    done: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    policy_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="dqn_episodes")
    slate: Mapped[Optional["ServedSlate"]] = relationship()

    __table_args__ = (
        Index("idx_dqn_episodes_episode", "episode_id"),
        Index("idx_dqn_episodes_user_time", "user_id", created_at.desc()),
        Index("idx_dqn_episodes_slate", "slate_id"),
    )


class HybridWeights(Base):
    """Active and historical Hybrid fusion weights."""

    __tablename__ = "hybrid_weights"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    alpha: Mapped[float] = mapped_column(Float, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    gamma: Mapped[float] = mapped_column(Float, nullable=False)
    ndcg_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_hybrid_weights_active", "active"),
        Index("idx_hybrid_weights_created", "created_at"),
    )


class HybridRequestLog(Base):
    """Hybrid per-request latency, downstream, and cost observability log."""

    __tablename__ = "hybrid_request_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    returned_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    downstream_status: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_hybrid_request_log_user_time", "user_id", created_at.desc()),
        Index("idx_hybrid_request_log_created", "created_at"),
    )


class SkillGapSnapshot(Base):
    """Historical skill-gap output shown to a user."""

    __tablename__ = "skill_gap_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    missing_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False)
    matched_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_skill_gap_user_time", "user_id", created_at.desc()),
    )


class Experiment(Base):
    """A/B experiment definition."""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variants: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'draft'"), nullable=False
    )
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    target_metric: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created", created_at.desc()),
    )


class ExperimentAssignment(Base):
    """User-to-variant assignment for an experiment."""

    __tablename__ = "experiment_assignments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    variant_name: Mapped[str] = mapped_column(String(60), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("experiment_id", "user_id", name="idx_experiment_assignments_unique"),
        Index("idx_experiment_assignments_variant", "experiment_id", "variant_name"),
    )


class ExperimentMetric(Base):
    """Pre-aggregated metric snapshot for an experiment variant."""

    __tablename__ = "experiment_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_name: Mapped[str] = mapped_column(String(60), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_experiment_metrics_lookup", "experiment_id", "variant_name", "metric_name"),
    )


# ════════════════════════════════════════════════════════════════
# Engine & Session Factories
# ════════════════════════════════════════════════════════════════

# Default connection URL (overridden by environment variable)
_DEFAULT_DATABASE_URL = "postgresql+asyncpg://localhost/scpa_db"


def get_database_url() -> str:
    """Resolve the async database URL from environment.

    Converts ``postgresql://`` or ``postgresql+psycopg2://`` prefixes
    to ``postgresql+asyncpg://`` for async driver compatibility.

    Returns:
        Fully-qualified async database connection URL.
    """
    url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    # Normalise to asyncpg driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url


def get_async_engine(url: Optional[str] = None):
    """Create an async SQLAlchemy engine.

    Args:
        url: Database URL. If None, resolved from environment.

    Returns:
        An ``AsyncEngine`` instance with connection pooling.
    """
    db_url = url or get_database_url()
    return create_async_engine(
        db_url,
        echo=os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_async_session_factory(engine=None) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: An ``AsyncEngine``. If None, creates one from env.

    Returns:
        An ``async_sessionmaker`` bound to the engine.
    """
    if engine is None:
        engine = get_async_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def get_sync_database_url() -> str:
    """Resolve the sync database URL for Alembic migrations.

    Returns:
        Fully-qualified sync database connection URL using psycopg2.
    """
    url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    # Normalise to psycopg2 driver
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url
