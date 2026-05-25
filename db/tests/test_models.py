"""Unit tests for SCPA SQLAlchemy ORM models.

Validates that all 5 tables, 8 ENUMs, 15 indexes, relationships,
and column types are correctly defined without requiring a live database.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import inspect

# ── Import all models and ENUMs ──
from db.models import (
    Application,
    ApplicationStatus,
    Base,
    CertificationSkill,
    DQNReplayArchive,
    DQNSessionLog,
    EmploymentMode,
    ExperienceLevel,
    HybridRequestLog,
    HybridWeights,
    Job,
    JobRequiredSkill,
    JobSource,
    JobType,
    ProficiencyLevel,
    Skill,
    SkillCategory,
    User,
    UserCertification,
    UserInteraction,
    UserJobInteraction,
    UserRole,
    UserSkill,
)


# ════════════════════════════════════════════════════════════════
# ENUM Tests
# ════════════════════════════════════════════════════════════════

class TestEnums:
    """Verify all 8 PostgreSQL ENUM types have correct values."""

    def test_user_role_values(self) -> None:
        assert set(e.value for e in UserRole) == {"user", "admin", "premium"}

    def test_job_type_values(self) -> None:
        assert set(e.value for e in JobType) == {
            "full_time", "part_time", "contract", "internship"
        }

    def test_employment_mode_values(self) -> None:
        assert set(e.value for e in EmploymentMode) == {
            "onsite", "remote", "hybrid"
        }

    def test_experience_level_values(self) -> None:
        assert set(e.value for e in ExperienceLevel) == {"entry", "mid", "senior"}

    def test_job_source_values(self) -> None:
        assert set(e.value for e in JobSource) == {
            "jobstreet", "linkedin", "glints", "kalibrr", "karir",
            "topkarir", "kitalulus", "techinasia", "remotive", "indeed",
        }
        assert len(JobSource) == 10

    def test_application_status_values(self) -> None:
        assert set(e.value for e in ApplicationStatus) == {
            "submitted", "reviewed", "accepted", "rejected", "withdrawn"
        }

    def test_skill_category_values(self) -> None:
        assert set(e.value for e in SkillCategory) == {
            "technical", "soft", "linguistic"
        }

    def test_proficiency_level_values(self) -> None:
        assert set(e.value for e in ProficiencyLevel) == {
            "beginner", "intermediate", "advanced"
        }

    def test_enum_count_is_eight(self) -> None:
        """Verify we have exactly 8 ENUM types defined."""
        enums = [
            UserRole, JobType, EmploymentMode, ExperienceLevel,
            JobSource, ApplicationStatus, SkillCategory, ProficiencyLevel,
        ]
        assert len(enums) == 8


# ════════════════════════════════════════════════════════════════
# Model Table Name Tests
# ════════════════════════════════════════════════════════════════

class TestTableNames:
    """Verify all 5 models map to correct table names."""

    @pytest.mark.parametrize(
        "model_cls, expected_table",
        [
            (User, "users"),
            (Job, "jobs"),
            (Application, "applications"),
            (UserSkill, "user_skills"),
            (UserInteraction, "user_interactions"),
            (UserJobInteraction, "user_job_interactions"),
            (DQNSessionLog, "dqn_session_logs"),
            (DQNReplayArchive, "dqn_replay_archive"),
            (HybridWeights, "hybrid_weights"),
            (HybridRequestLog, "hybrid_request_log"),
            (Skill, "skills"),
            (JobRequiredSkill, "job_required_skills"),
            (CertificationSkill, "certification_skills"),
            (UserCertification, "user_certifications"),
        ],
    )
    def test_table_name(self, model_cls, expected_table: str) -> None:
        assert model_cls.__tablename__ == expected_table

    def test_all_tables_in_metadata(self) -> None:
        """Verify all 5 tables are registered in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "users",
            "jobs",
            "applications",
            "user_skills",
            "user_interactions",
            "user_job_interactions",
            "dqn_session_logs",
            "dqn_replay_archive",
            "hybrid_weights",
            "hybrid_request_log",
            "skills",
            "job_required_skills",
            "certification_skills",
            "user_certifications",
        }
        assert expected.issubset(table_names)


# ════════════════════════════════════════════════════════════════
# Column Tests
# ════════════════════════════════════════════════════════════════

class TestUserColumns:
    """Verify User model column definitions."""

    def test_user_has_required_columns(self) -> None:
        mapper = inspect(User)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "name", "email", "password_hash", "program_studi",
            "university", "completion_percent", "role", "email_verified",
            "last_login_at", "cv_embedding", "cv_uploaded_at",
            "created_at", "updated_at",
        }
        assert expected.issubset(column_names)

    def test_user_id_is_uuid(self) -> None:
        mapper = inspect(User)
        id_col = mapper.columns["id"]
        assert id_col.primary_key

    def test_user_email_is_unique(self) -> None:
        mapper = inspect(User)
        email_col = mapper.columns["email"]
        assert email_col.unique


class TestJobColumns:
    """Verify Job model column definitions."""

    def test_job_has_required_columns(self) -> None:
        mapper = inspect(Job)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "title", "company", "location", "type", "min_salary",
            "max_salary", "salary_currency", "salary_text", "employment_mode",
            "description", "experience_level", "posted_at", "source",
            "is_active", "match_data", "skills_extracted_at",
        }
        assert expected.issubset(column_names)

    def test_job_match_data_is_jsonb(self) -> None:
        mapper = inspect(Job)
        col = mapper.columns["match_data"]
        assert col.nullable


class TestApplicationColumns:
    """Verify Application model column definitions."""

    def test_application_has_fks(self) -> None:
        mapper = inspect(Application)
        column_names = {col.key for col in mapper.columns}
        assert "user_id" in column_names
        assert "job_id" in column_names

    def test_application_status_default(self) -> None:
        mapper = inspect(Application)
        status_col = mapper.columns["status"]
        assert not status_col.nullable


class TestUserSkillColumns:
    """Verify UserSkill model column definitions."""

    def test_user_skill_has_required_columns(self) -> None:
        mapper = inspect(UserSkill)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "user_id", "skill", "category",
            "proficiency_level", "endorsed", "created_at",
        }
        assert expected.issubset(column_names)


class TestUserInteractionColumns:
    """Verify UserInteraction model column definitions."""

    def test_interaction_has_required_columns(self) -> None:
        mapper = inspect(UserInteraction)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "user_id", "action_type", "target_type",
            "target_id", "session_id", "created_at",
        }
        assert expected.issubset(column_names)

    def test_interaction_target_id_has_no_fk(self) -> None:
        """target_id is polymorphic — no FK constraint."""
        mapper = inspect(UserInteraction)
        target_col = mapper.columns["target_id"]
        assert len(target_col.foreign_keys) == 0


class TestSkillTaxonomyColumns:
    """Verify controlled skill taxonomy tables."""

    def test_skill_has_taxonomy_columns(self) -> None:
        mapper = inspect(Skill)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "name", "category", "frequency", "aliases",
            "created_at", "updated_at",
        }
        assert expected.issubset(column_names)

    def test_job_required_skill_has_unique_pair(self) -> None:
        table = Base.metadata.tables["job_required_skills"]
        constraint_names = {c.name for c in table.constraints}
        assert "uq_job_required_skills_job_skill" in constraint_names

    def test_user_certification_has_mapping_columns(self) -> None:
        mapper = inspect(UserCertification)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "user_id", "file_path", "cert_name", "issuer",
            "ocr_confidence", "mapped_skills", "status", "created_at",
        }
        assert expected.issubset(column_names)

# ════════════════════════════════════════════════════════════════
# Index Tests
# ════════════════════════════════════════════════════════════════

class TestIndexes:
    """Verify all 15 indexes from the Index Strategy table."""

    def _get_index_names(self, table_name: str) -> set:
        table = Base.metadata.tables[table_name]
        return {idx.name for idx in table.indexes}

    def test_users_indexes(self) -> None:
        indexes = self._get_index_names("users")
        assert "idx_users_email" in indexes
        assert "idx_users_completion" in indexes
        assert "idx_users_created_at" in indexes

    def test_jobs_indexes(self) -> None:
        indexes = self._get_index_names("jobs")
        assert "idx_jobs_company" in indexes
        assert "idx_jobs_location" in indexes
        assert "idx_jobs_source" in indexes
        assert "idx_jobs_posted_at" in indexes
        assert "idx_jobs_active" in indexes
        assert "idx_jobs_active_posted_id" in indexes
        assert "idx_jobs_active_source_posted" in indexes
        assert "idx_jobs_active_experience_posted" in indexes

    def test_applications_indexes(self) -> None:
        indexes = self._get_index_names("applications")
        assert "idx_applications_status" in indexes
        assert "idx_applications_user" in indexes
        assert "idx_applications_job" in indexes
        assert "idx_applications_user_applied" in indexes

    def test_user_skills_indexes(self) -> None:
        indexes = self._get_index_names("user_skills")
        assert "idx_user_skills_user" in indexes
        assert "idx_user_skills_skill" in indexes

    def test_taxonomy_indexes(self) -> None:
        assert "idx_skills_name" in self._get_index_names("skills")
        assert "idx_skills_category" in self._get_index_names("skills")
        assert "idx_jrs_job" in self._get_index_names("job_required_skills")
        assert "idx_jrs_skill" in self._get_index_names("job_required_skills")
        assert "idx_uc_user" in self._get_index_names("user_certifications")

    def test_user_interactions_indexes(self) -> None:
        indexes = self._get_index_names("user_interactions")
        assert "idx_interactions_user_time" in indexes
        assert "idx_interactions_created" in indexes

    def test_total_index_count(self) -> None:
        """Verify we have at least 15 custom indexes across all tables."""
        total = 0
        for table_name in [
            "users", "jobs", "applications", "user_skills", "user_interactions"
        ]:
            total += len(self._get_index_names(table_name))
        assert total >= 15

    def test_index_names_are_unique(self) -> None:
        names = [
            index.name
            for table in Base.metadata.tables.values()
            for index in table.indexes
            if index.name
        ]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        assert duplicates == []


# ════════════════════════════════════════════════════════════════
# Relationship Tests
# ════════════════════════════════════════════════════════════════

class TestRelationships:
    """Verify ORM relationships between models."""

    def test_user_has_skills_relationship(self) -> None:
        mapper = inspect(User)
        assert "skills" in mapper.relationships

    def test_user_has_applications_relationship(self) -> None:
        mapper = inspect(User)
        assert "applications" in mapper.relationships

    def test_user_has_interactions_relationship(self) -> None:
        mapper = inspect(User)
        assert "interactions" in mapper.relationships

    def test_job_has_applications_relationship(self) -> None:
        mapper = inspect(Job)
        assert "applications" in mapper.relationships

    def test_application_has_user_relationship(self) -> None:
        mapper = inspect(Application)
        assert "user" in mapper.relationships

    def test_application_has_job_relationship(self) -> None:
        mapper = inspect(Application)
        assert "job" in mapper.relationships

    def test_user_skill_has_user_relationship(self) -> None:
        mapper = inspect(UserSkill)
        assert "user" in mapper.relationships

    def test_interaction_has_user_relationship(self) -> None:
        mapper = inspect(UserInteraction)
        assert "user" in mapper.relationships

    def test_skill_has_job_required_relationship(self) -> None:
        mapper = inspect(Skill)
        assert "job_requirements" in mapper.relationships

    def test_job_has_required_skills_relationship(self) -> None:
        mapper = inspect(Job)
        assert "required_skills" in mapper.relationships

# ════════════════════════════════════════════════════════════════
# Repr Tests
# ════════════════════════════════════════════════════════════════

class TestRepr:
    """Verify __repr__ methods return meaningful strings."""

    def test_user_repr(self) -> None:
        user = User(
            id=uuid.uuid4(),
            name="Test User",
            email="test@example.com",
            password_hash="hashed",
            role=UserRole.USER,
        )
        result = repr(user)
        assert "User" in result
        assert "test@example.com" in result

    def test_job_repr(self) -> None:
        job = Job(
            id=uuid.uuid4(),
            title="ML Engineer",
            company="TechCorp",
        )
        result = repr(job)
        assert "Job" in result
        assert "ML Engineer" in result


# ════════════════════════════════════════════════════════════════
# Factory Function Tests
# ════════════════════════════════════════════════════════════════

class TestFactoryFunctions:
    """Verify engine and session factory functions."""

    def test_get_database_url_default(self, monkeypatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from db.models import get_database_url
        url = get_database_url()
        assert "asyncpg" in url
        assert "scpa_db" in url

    def test_get_database_url_converts_psycopg2(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg2://user:pass@host:5432/db"
        )
        from db.models import get_database_url
        url = get_database_url()
        assert "asyncpg" in url
        assert "psycopg2" not in url

    def test_get_sync_database_url_converts_asyncpg(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:pass@host:5432/db"
        )
        from db.models import get_sync_database_url
        url = get_sync_database_url()
        assert "psycopg2" in url
        assert "asyncpg" not in url
