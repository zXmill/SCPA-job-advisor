"""Add ML infrastructure tables for NCF, DQN, and Hybrid services."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_ml_infra_tables"
down_revision = "002_extend_jobsource_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_job_interactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clicked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("saved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applied", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dwell_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_job_interaction"),
    )
    op.create_index(
        "idx_user_job_interactions_user",
        "user_job_interactions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_user_job_interactions_job", "user_job_interactions", ["job_id"])

    op.create_table(
        "dqn_session_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_history", postgresql.JSONB(), nullable=True),
        sa.Column("candidate_jobs", postgresql.JSONB(), nullable=True),
        sa.Column("rewards", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_dqn_session_logs_session", "dqn_session_logs", ["session_id"])
    op.create_index(
        "idx_dqn_session_logs_user_time",
        "dqn_session_logs",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "dqn_replay_archive",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("action", sa.Integer(), nullable=False),
        sa.Column("reward", sa.Float(), nullable=False),
        sa.Column("next_state", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_dqn_replay_archive_created", "dqn_replay_archive", ["created_at"])
    op.create_index("idx_dqn_replay_archive_user", "dqn_replay_archive", ["user_id"])

    op.create_table(
        "hybrid_weights",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("gamma", sa.Float(), nullable=False),
        sa.Column("ndcg_score", sa.Float(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_hybrid_weights_active", "hybrid_weights", ["active"])
    op.create_index("idx_hybrid_weights_created", "hybrid_weights", ["created_at"])

    op.create_table(
        "hybrid_request_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("returned_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("downstream_status", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(
        "idx_hybrid_request_log_user_time",
        "hybrid_request_log",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_hybrid_request_log_created", "hybrid_request_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_hybrid_request_log_created", table_name="hybrid_request_log")
    op.drop_index("idx_hybrid_request_log_user_time", table_name="hybrid_request_log")
    op.drop_table("hybrid_request_log")

    op.drop_index("idx_hybrid_weights_created", table_name="hybrid_weights")
    op.drop_index("idx_hybrid_weights_active", table_name="hybrid_weights")
    op.drop_table("hybrid_weights")

    op.drop_index("idx_dqn_replay_archive_user", table_name="dqn_replay_archive")
    op.drop_index("idx_dqn_replay_archive_created", table_name="dqn_replay_archive")
    op.drop_table("dqn_replay_archive")

    op.drop_index("idx_dqn_session_logs_user_time", table_name="dqn_session_logs")
    op.drop_index("idx_dqn_session_logs_session", table_name="dqn_session_logs")
    op.drop_table("dqn_session_logs")

    op.drop_index("idx_user_job_interactions_job", table_name="user_job_interactions")
    op.drop_index("idx_user_job_interactions_user", table_name="user_job_interactions")
    op.drop_table("user_job_interactions")
