"""add job stage and deadline

Revision ID: 0007_job_stage_deadline
Revises: 0006_companies_jobs
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_job_stage_deadline"
down_revision = "0006_companies_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("stage", sa.String(length=32), nullable=False, server_default="saved"))
    op.add_column("jobs", sa.Column("deadline", sa.Date(), nullable=True))
    op.create_index("ix_jobs_stage", "jobs", ["stage"], unique=False)
    op.create_index("ix_jobs_deadline", "jobs", ["deadline"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_deadline", table_name="jobs")
    op.drop_index("ix_jobs_stage", table_name="jobs")
    op.drop_column("jobs", "deadline")
    op.drop_column("jobs", "stage")
