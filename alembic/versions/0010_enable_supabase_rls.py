"""enable RLS for Supabase exposed tables

Revision ID: 0010_enable_supabase_rls
Revises: 0009_project_job_embeddings
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_enable_supabase_rls"
down_revision = "0009_project_job_embeddings"
branch_labels = None
depends_on = None


RLS_TABLES = (
    "alembic_version",
    "users",
    "google_credentials",
    "resumes",
    "generated_documents",
    "user_sessions",
    "oauth_states",
    "oauth_login_states",
    "profiles",
    "educations",
    "projects",
    "companies",
    "jobs",
    "public_portfolios",
    "project_embeddings",
    "job_embeddings",
)


def upgrade() -> None:
    conn = op.get_bind()
    for table_name in RLS_TABLES:
        conn.execute(sa.text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    conn = op.get_bind()
    for table_name in reversed(RLS_TABLES):
        conn.execute(sa.text(f'ALTER TABLE public."{table_name}" DISABLE ROW LEVEL SECURITY'))
