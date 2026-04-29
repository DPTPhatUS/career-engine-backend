"""enforce 1:1 resume documents

Revision ID: 0005_resume_doc_unique
Revises: 0004_profile_education_project
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_resume_doc_unique"
down_revision = "0004_profile_education_project"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    resume_id,
                    created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY resume_id
                        ORDER BY created_at DESC, id DESC
                    ) AS rn
                FROM generated_documents
            )
            DELETE FROM generated_documents
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )

    op.drop_index("ix_generated_documents_resume_id", table_name="generated_documents")
    op.create_index(
        "ix_generated_documents_resume_id",
        "generated_documents",
        ["resume_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_generated_documents_resume_id", table_name="generated_documents")
    op.create_index(
        "ix_generated_documents_resume_id",
        "generated_documents",
        ["resume_id"],
        unique=False,
    )

