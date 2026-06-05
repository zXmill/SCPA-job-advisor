"""SCPA Database Package.

Exports all ORM models, ENUMs, and session factories for use
across the SCPA microservices platform.

Usage::

    from db.models import Base, User, Job, Application, UserSkill, UserInteraction
    from db.models import get_async_engine, get_async_session_factory
"""

from db.models import (
    # Base
    Base,
    # ENUMs
    ApplicationStatus,
    EmploymentMode,
    ExperienceLevel,
    JobSource,
    JobType,
    ProficiencyLevel,
    SkillCategory,
    UserRole,
    # Models
    Application,
    CertificationSkill,
    DQNEpisode,
    DQNReplayArchive,
    DQNSessionLog,
    EmbeddingCacheEntry,
    FeedbackEvent,
    HybridRequestLog,
    HybridWeights,
    Job,
    JobRequiredSkill,
    ModelArtifact,
    ModelEntityMapping,
    ServedSlate,
    ServedSlateItem,
    Skill,
    User,
    UserCertification,
    UserInteraction,
    UserJobInteraction,
    UserSkill,
    # Factories
    get_async_engine,
    get_async_session_factory,
    get_database_url,
    get_sync_database_url,
)

__all__ = [
    "Base",
    # ENUMs
    "ApplicationStatus",
    "EmploymentMode",
    "ExperienceLevel",
    "JobSource",
    "JobType",
    "ProficiencyLevel",
    "SkillCategory",
    "UserRole",
    # Models
    "Application",
    "CertificationSkill",
    "DQNEpisode",
    "DQNReplayArchive",
    "DQNSessionLog",
    "EmbeddingCacheEntry",
    "FeedbackEvent",
    "HybridRequestLog",
    "HybridWeights",
    "Job",
    "JobRequiredSkill",
    "ModelArtifact",
    "ModelEntityMapping",
    "ServedSlate",
    "ServedSlateItem",
    "Skill",
    "User",
    "UserCertification",
    "UserInteraction",
    "UserJobInteraction",
    "UserSkill",
    # Factories
    "get_async_engine",
    "get_async_session_factory",
    "get_database_url",
    "get_sync_database_url",
]
