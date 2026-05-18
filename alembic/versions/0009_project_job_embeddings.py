"""add project and job embeddings

Revision ID: 0009_project_job_embeddings
Revises: 0008_public_portfolios
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_project_job_embeddings"
down_revision = "0008_public_portfolios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "embedding_model", name="uq_project_embedding_model"),
    )
    op.create_index("ix_project_embeddings_user_id", "project_embeddings", ["user_id"], unique=False)
    op.create_index("ix_project_embeddings_project_id", "project_embeddings", ["project_id"], unique=False)

    op.create_table(
        "job_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "embedding_model", name="uq_job_embedding_model"),
    )
    op.create_index("ix_job_embeddings_user_id", "job_embeddings", ["user_id"], unique=False)
    op.create_index("ix_job_embeddings_job_id", "job_embeddings", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_embeddings_job_id", table_name="job_embeddings")
    op.drop_index("ix_job_embeddings_user_id", table_name="job_embeddings")
    op.drop_table("job_embeddings")

    op.drop_index("ix_project_embeddings_project_id", table_name="project_embeddings")
    op.drop_index("ix_project_embeddings_user_id", table_name="project_embeddings")
    op.drop_table("project_embeddings")
