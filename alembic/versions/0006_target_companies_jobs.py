"""add target companies and jobs

Revision ID: 0006_target_companies_jobs
Revises: 0005_resume_doc_unique
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_target_companies_jobs"
down_revision = "0005_resume_doc_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company_url", sa.String(length=1000), nullable=True),
        sa.Column("overview", sa.String(length=8000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_target_companies_user_id", "target_companies", ["user_id"], unique=False)
    op.create_index("ix_target_companies_sort_order", "target_companies", ["sort_order"], unique=False)

    op.create_table(
        "target_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("target_companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("job_description", sa.String(length=8000), nullable=False),
        sa.Column("job_requirements", sa.String(length=8000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_target_jobs_user_id", "target_jobs", ["user_id"], unique=False)
    op.create_index("ix_target_jobs_company_id", "target_jobs", ["company_id"], unique=False)
    op.create_index("ix_target_jobs_sort_order", "target_jobs", ["sort_order"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_target_jobs_sort_order", table_name="target_jobs")
    op.drop_index("ix_target_jobs_company_id", table_name="target_jobs")
    op.drop_index("ix_target_jobs_user_id", table_name="target_jobs")
    op.drop_table("target_jobs")

    op.drop_index("ix_target_companies_sort_order", table_name="target_companies")
    op.drop_index("ix_target_companies_user_id", table_name="target_companies")
    op.drop_table("target_companies")
