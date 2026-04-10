"""add oauth login states and user sessions

Revision ID: 0002_auth_sessions
Revises: 0001_initial
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_auth_sessions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_login_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("next_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("state", name="uq_oauth_login_state"),
    )
    op.create_index("ix_oauth_login_states_state", "oauth_login_states", ["state"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_user_session_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index("ix_oauth_login_states_state", table_name="oauth_login_states")
    op.drop_table("oauth_login_states")
