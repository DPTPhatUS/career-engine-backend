"""add profile education and project tables

Revision ID: 0004_profile_education_project
Revises: 0003_oauth_pkce_verifier
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_profile_education_project"
down_revision = "0003_oauth_pkce_verifier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("github_label", sa.String(length=64), nullable=True),
        sa.Column("github_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], unique=True)

    op.create_table(
        "educations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("university", sa.String(length=255), nullable=False),
        sa.Column("degree", sa.String(length=255), nullable=False),
        sa.Column("field", sa.String(length=255), nullable=False),
        sa.Column("time_period", sa.String(length=100), nullable=False),
        sa.Column("gpa", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("relevant_coursework", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_educations_user_id", "educations", ["user_id"], unique=False)
    op.create_index("ix_educations_sort_order", "educations", ["sort_order"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("date_range", sa.String(length=100), nullable=False),
        sa.Column("github_url", sa.String(length=1000), nullable=True),
        sa.Column("tech_stack", sa.String(length=500), nullable=True),
        sa.Column("bullets", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)
    op.create_index("ix_projects_sort_order", "projects", ["sort_order"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_projects_sort_order", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_educations_sort_order", table_name="educations")
    op.drop_index("ix_educations_user_id", table_name="educations")
    op.drop_table("educations")

    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")