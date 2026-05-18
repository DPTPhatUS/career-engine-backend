"""add public portfolios

Revision ID: 0008_public_portfolios
Revises: 0007_job_stage_deadline
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_public_portfolios"
down_revision = "0007_job_stage_deadline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_portfolios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_resume_id", sa.String(length=36), nullable=True),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_portfolios_user_id", "public_portfolios", ["user_id"], unique=False)
    op.create_index("ix_public_portfolios_source_resume_id", "public_portfolios", ["source_resume_id"], unique=True)
    op.create_index("ix_public_portfolios_slug", "public_portfolios", ["slug"], unique=True)
    op.create_index("ix_public_portfolios_is_published", "public_portfolios", ["is_published"], unique=False)
    op.create_index("ix_public_portfolios_published_at", "public_portfolios", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_public_portfolios_published_at", table_name="public_portfolios")
    op.drop_index("ix_public_portfolios_is_published", table_name="public_portfolios")
    op.drop_index("ix_public_portfolios_slug", table_name="public_portfolios")
    op.drop_index("ix_public_portfolios_source_resume_id", table_name="public_portfolios")
    op.drop_index("ix_public_portfolios_user_id", table_name="public_portfolios")
    op.drop_table("public_portfolios")
