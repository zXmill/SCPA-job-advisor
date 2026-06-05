#!/usr/bin/env python3
"""SCPA Initial Migration

Creates all core tables for the SCPA platform.
Run: alembic revision --autogenerate -m "initial_schema"
    or: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
import uuid

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Users table
    op.create_table('users',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(128), nullable=False),
        sa.Column('program_studi', sa.String(255), nullable=True),
        sa.Column('university', sa.String(255), nullable=True),
        sa.Column('completion_percent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('role', sa.Enum('user', 'admin', 'premium', name='userrole'), server_default='user', nullable=False),
        sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes on users
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_completion', 'users', ['completion_percent'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])

    # Jobs table
    op.create_table('jobs',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('type', sa.Enum('full_time', 'part_time', 'contract', 'internship', name='jobtype'), nullable=True),
        sa.Column('min_salary', sa.Float(), nullable=True),
        sa.Column('max_salary', sa.Float(), nullable=True),
        sa.Column('salary_currency', sa.String(3), server_default='IDR', nullable=False),
        sa.Column('employment_mode', sa.Enum('onsite', 'remote', 'hybrid', name='employmentmode'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('experience_level', sa.Enum('entry', 'mid', 'senior', name='experiencelevel'), nullable=True),
        sa.Column('posted_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('source', sa.Enum('jobstreet', 'linkedin', 'glints', name='jobsource'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('match_data', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes on jobs
    op.create_index('idx_jobs_company', 'jobs', ['company'])
    op.create_index('idx_jobs_location', 'jobs', ['location'])
    op.create_index('idx_jobs_source', 'jobs', ['source'])
    op.create_index('idx_jobs_posted_at', 'jobs', ['posted_at'])
    op.create_index('idx_jobs_active', 'jobs', ['is_active'], postgresql_where=sa.text("is_active = true"))

    # Applications table
    op.create_table('applications',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('submitted', 'reviewed', 'accepted', 'rejected', 'withdrawn', name='applicationstatus'), server_default='submitted', nullable=False),
        sa.Column('cover_letter', sa.Text(), nullable=True),
        sa.Column('resume_url', sa.String(500), nullable=True),
        sa.Column('applied_via', sa.String(20), server_default='web', nullable=False),
        sa.Column('applied_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'job_id', name='uq_user_job'),
    )

    op.create_index('idx_applications_status', 'applications', ['status'])
    op.create_index('idx_applications_user', 'applications', ['user_id'])
    op.create_index('idx_applications_job', 'applications', ['job_id'])

    # User Skills table
    op.create_table('user_skills',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('skill', sa.String(100), nullable=False),
        sa.Column('category', sa.Enum('technical', 'soft', 'linguistic', name='skillcategory'), server_default='technical', nullable=False),
        sa.Column('proficiency_level', sa.Enum('beginner', 'intermediate', 'advanced', name='proficiencylevel'), server_default='beginner', nullable=False),
        sa.Column('endorsed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_user_skills_user', 'user_skills', ['user_id', 'skill'], unique=True)
    op.create_index('idx_user_skills_skill', 'user_skills', ['skill'])

    # User Interactions table
    op.create_table('user_interactions',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(30), nullable=False),
        sa.Column('target_id', UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_interactions_user_time', 'user_interactions', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_interactions_created', 'user_interactions', ['created_at'])


def downgrade():
    op.drop_index('idx_interactions_created', 'user_interactions')
    op.drop_index('idx_interactions_user_time', 'user_interactions')
    op.drop_table('user_interactions')
    op.drop_index('idx_user_skills_skill', 'user_skills')
    op.drop_index('idx_user_skills_user', 'user_skills')
    op.drop_table('user_skills')
    op.drop_index('idx_applications_job', 'applications')
    op.drop_index('idx_applications_user', 'applications')
    op.drop_index('idx_applications_status', 'applications')
    op.drop_table('applications')
    op.drop_index('idx_jobs_active', 'jobs')
    op.drop_index('idx_jobs_posted_at', 'jobs')
    op.drop_index('idx_jobs_source', 'jobs')
    op.drop_index('idx_jobs_location', 'jobs')
    op.drop_index('idx_jobs_company', 'jobs')
    op.drop_table('jobs')
    op.drop_index('idx_users_created_at', 'users')
    op.drop_index('idx_users_completion', 'users')
    op.drop_index('idx_users_email', 'users')
    op.drop_table('users')

    # Drop ENUMs
    for enum_name in ['userrole', 'jobtype', 'employmentmode', 'experiencelevel',
                      'jobsource', 'applicationstatus', 'skillcategory', 'proficiencylevel']:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')