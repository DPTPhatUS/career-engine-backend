"""add oauth pkce code verifier columns

Revision ID: 0003_oauth_pkce_verifier
Revises: 0002_auth_sessions
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_oauth_pkce_verifier"
down_revision = "0002_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("oauth_states", sa.Column("code_verifier", sa.String(length=255), nullable=True))
    op.add_column("oauth_login_states", sa.Column("code_verifier", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("oauth_login_states", "code_verifier")
    op.drop_column("oauth_states", "code_verifier")
