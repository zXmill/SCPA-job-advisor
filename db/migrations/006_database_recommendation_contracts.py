"""Add recommendation evidence persistence contracts.

Revision ID: 006_reco_db_contracts
Revises: 005_add_salary_text
Create Date: 2026-05-25 13:00:00.000000

Adds DATABASE wave tables for exposure-aware feedback, served slate logging,
model artifact lineage, SBERT embedding cache rows, stable model entity
mappings, and DQN MDP episodes.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006_reco_db_contracts"
down_revision: Union[str, None] = "005_add_salary_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "served_slates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("pipeline_run_id", sa.String(length=64), nullable=True),
        sa.Column(
            "model_versions",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fallback_flags",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_served_slates_user_time",
        "served_slates",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_served_slates_pipeline_run", "served_slates", ["pipeline_run_id"])

    op.create_table(
        "served_slate_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("slate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("component_scores", postgresql.JSONB(), nullable=True),
        sa.Column(
            "model_versions",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fallback_flags",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("explanation", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["slate_id"], ["served_slates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slate_id", "rank", name="uq_served_slate_rank"),
    )
    op.create_index(
        "idx_served_slate_items_slate_rank",
        "served_slate_items",
        ["slate_id", "rank"],
    )
    op.create_index("idx_served_slate_items_job", "served_slate_items", ["job_id"])

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slate_item_id", sa.BigInteger(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("dwell_ms", sa.Integer(), nullable=True),
        sa.Column(
            "model_provenance",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fallback_flags",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["slate_id"], ["served_slates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["slate_item_id"], ["served_slate_items.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "idx_feedback_events_user_time",
        "feedback_events",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_feedback_events_slate_rank", "feedback_events", ["slate_id", "rank"])
    op.create_index(
        "idx_feedback_events_type_time",
        "feedback_events",
        ["event_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_feedback_events_job_time",
        "feedback_events",
        ["job_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "model_artifacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=True),
        sa.Column("training_run_id", sa.String(length=100), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("fallback_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint(
            "service",
            "model_version",
            "artifact_path",
            name="uq_model_artifact_version_path",
        ),
    )
    op.create_index(
        "idx_model_artifacts_service_version",
        "model_artifacts",
        ["service", "model_version"],
    )
    op.create_index(
        "idx_model_artifacts_active",
        "model_artifacts",
        ["service", "active"],
        postgresql_where=sa.text("active = true"),
    )
    op.create_index("idx_model_artifacts_created", "model_artifacts", ["created_at"])

    op.create_table(
        "embedding_cache_entries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("cache_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("source_text_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("service", sa.String(length=32), server_default=sa.text("'sbert'"), nullable=False),
        sa.Column("fallback_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(
        "idx_embedding_cache_model_version",
        "embedding_cache_entries",
        ["model_version"],
    )
    op.create_index(
        "idx_embedding_cache_text_hash",
        "embedding_cache_entries",
        ["source_text_hash"],
    )
    op.create_index("idx_embedding_cache_expires", "embedding_cache_entries", ["expires_at"])

    op.create_table(
        "model_entity_mappings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internal_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint(
            "service",
            "model_version",
            "entity_type",
            "external_id",
            name="uq_model_entity_external",
        ),
        sa.UniqueConstraint(
            "service",
            "model_version",
            "entity_type",
            "internal_index",
            name="uq_model_entity_internal_index",
        ),
    )
    op.create_index(
        "idx_model_entity_mapping_lookup",
        "model_entity_mappings",
        ["service", "model_version", "entity_type"],
    )

    op.create_table(
        "dqn_episodes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "episode_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("reward", sa.Float(), nullable=False),
        sa.Column("next_state", postgresql.JSONB(), nullable=True),
        sa.Column("done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["slate_id"], ["served_slates.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_dqn_episodes_episode", "dqn_episodes", ["episode_id"])
    op.create_index(
        "idx_dqn_episodes_user_time",
        "dqn_episodes",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_dqn_episodes_slate", "dqn_episodes", ["slate_id"])


def downgrade() -> None:
    op.drop_index("idx_dqn_episodes_slate", table_name="dqn_episodes")
    op.drop_index("idx_dqn_episodes_user_time", table_name="dqn_episodes")
    op.drop_index("idx_dqn_episodes_episode", table_name="dqn_episodes")
    op.drop_table("dqn_episodes")

    op.drop_index("idx_model_entity_mapping_lookup", table_name="model_entity_mappings")
    op.drop_table("model_entity_mappings")

    op.drop_index("idx_embedding_cache_expires", table_name="embedding_cache_entries")
    op.drop_index("idx_embedding_cache_text_hash", table_name="embedding_cache_entries")
    op.drop_index("idx_embedding_cache_model_version", table_name="embedding_cache_entries")
    op.drop_table("embedding_cache_entries")

    op.drop_index("idx_model_artifacts_created", table_name="model_artifacts")
    op.drop_index("idx_model_artifacts_active", table_name="model_artifacts")
    op.drop_index("idx_model_artifacts_service_version", table_name="model_artifacts")
    op.drop_table("model_artifacts")

    op.drop_index("idx_feedback_events_job_time", table_name="feedback_events")
    op.drop_index("idx_feedback_events_type_time", table_name="feedback_events")
    op.drop_index("idx_feedback_events_slate_rank", table_name="feedback_events")
    op.drop_index("idx_feedback_events_user_time", table_name="feedback_events")
    op.drop_table("feedback_events")

    op.drop_index("idx_served_slate_items_job", table_name="served_slate_items")
    op.drop_index("idx_served_slate_items_slate_rank", table_name="served_slate_items")
    op.drop_table("served_slate_items")

    op.drop_index("idx_served_slates_pipeline_run", table_name="served_slates")
    op.drop_index("idx_served_slates_user_time", table_name="served_slates")
    op.drop_table("served_slates")
