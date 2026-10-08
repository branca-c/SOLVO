"""Add the exclusive public-demo session lease.

Revision ID: 20261008_0006
Revises: 20260930_0005
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20261008_0006"
down_revision = "20260930_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_demo_sessions_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text("INSERT INTO demo_sessions (id, generation) VALUES (1, 0)"))


def downgrade() -> None:
    op.drop_table("demo_sessions")
