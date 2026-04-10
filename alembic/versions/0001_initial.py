"""initial tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("state", name="uq_oauth_state"),
    )
    op.create_index("ix_oauth_states_state", "oauth_states", ["state"], unique=False)
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"], unique=False)

    op.create_table(
        "google_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_credentials_json", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_google_credentials_user_id", "google_credentials", ["user_id"], unique=True)

    op.create_table(
        "resumes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"], unique=False)
    op.create_index("ix_resumes_title", "resumes", ["title"], unique=False)

    op.create_table(
        "generated_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("resume_id", sa.String(length=36), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=255), nullable=False),
        sa.Column("document_url", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_generated_documents_resume_id", "generated_documents", ["resume_id"], unique=False)
    op.create_index("ix_generated_documents_user_id", "generated_documents", ["user_id"], unique=False)
    op.create_index("ix_generated_documents_document_id", "generated_documents", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_generated_documents_document_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_user_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_resume_id", table_name="generated_documents")
    op.drop_table("generated_documents")

    op.drop_index("ix_resumes_title", table_name="resumes")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.drop_table("resumes")

    op.drop_index("ix_google_credentials_user_id", table_name="google_credentials")
    op.drop_table("google_credentials")

    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state", table_name="oauth_states")
    op.drop_table("oauth_states")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
