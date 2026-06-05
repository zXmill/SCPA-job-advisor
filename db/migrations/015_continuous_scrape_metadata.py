"""Add continuous scrape metadata to jobs.

Revision ID: 015_continuous_scrape_metadata
Revises: 014_rich_job_desc_skill_sources
Create Date: 2026-06-01 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_continuous_scrape_metadata"
down_revision: Union[str, None] = "014_rich_job_desc_skill_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("scraped_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("first_seen_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "quality_status",
            sa.String(length=32),
            server_default=sa.text("'accepted'"),
            nullable=False,
        ),
    )
    op.add_column("jobs", sa.Column("quality_reject_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE jobs
        SET
            external_id = COALESCE(external_id, match_data->>'original_job_id'),
            scraped_at = COALESCE(scraped_at, posted_at, NOW()),
            first_seen_at = COALESCE(first_seen_at, posted_at, NOW()),
            last_seen_at = COALESCE(last_seen_at, posted_at, NOW()),
            quality_status = COALESCE(quality_status, 'accepted'),
            content_hash = COALESCE(
                content_hash,
                md5(
                    coalesce(title, '') || '|' ||
                    coalesce(company, '') || '|' ||
                    coalesce(source_url, '') || '|' ||
                    coalesce(description_text, description, '')
                )
            )
        """
    )
    op.execute(
        """
        WITH ranked_source_urls AS (
            SELECT
                id,
                source_url,
                row_number() OVER (
                    PARTITION BY source_url
                    ORDER BY
                        is_active DESC,
                        length(coalesce(nullif(description_text, ''), description, '')) DESC,
                        posted_at DESC NULLS LAST,
                        id
                ) AS row_rank
            FROM jobs
            WHERE source_url IS NOT NULL AND source_url <> ''
        )
        UPDATE jobs
        SET
            is_active = false,
            match_data = coalesce(match_data, '{}'::jsonb)
                || jsonb_build_object('deduplicated_source_url', jobs.source_url),
            source_url = NULL
        FROM ranked_source_urls
        WHERE jobs.id = ranked_source_urls.id
          AND ranked_source_urls.row_rank > 1
        """
    )
    op.create_index("idx_jobs_external_id", "jobs", ["external_id"])
    op.create_index("idx_jobs_last_seen_at", "jobs", ["last_seen_at"])
    op.create_index("idx_jobs_quality_status", "jobs", ["quality_status"])
    op.create_index("idx_jobs_content_hash", "jobs", ["content_hash"])
    # Build the new hot-path uniqueness contract without holding a long write lock.
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_jobs_source_url_present",
            "jobs",
            ["source_url"],
            unique=True,
            postgresql_concurrently=True,
            postgresql_where=sa.text("source_url IS NOT NULL AND source_url <> ''"),
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_jobs_source_url_present",
            table_name="jobs",
            postgresql_concurrently=True,
        )
    op.drop_index("idx_jobs_content_hash", table_name="jobs")
    op.drop_index("idx_jobs_quality_status", table_name="jobs")
    op.drop_index("idx_jobs_last_seen_at", table_name="jobs")
    op.drop_index("idx_jobs_external_id", table_name="jobs")
    op.drop_column("jobs", "content_hash")
    op.drop_column("jobs", "quality_reject_reason")
    op.drop_column("jobs", "quality_status")
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "first_seen_at")
    op.drop_column("jobs", "scraped_at")
    op.drop_column("jobs", "external_id")
