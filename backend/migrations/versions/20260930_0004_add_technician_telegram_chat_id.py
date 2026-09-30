"""Add an optional private Telegram destination to technicians.

Revision ID: 20260930_0004
Revises: 20260916_0003
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_0004"
down_revision = "20260916_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("technicians", sa.Column("telegram_chat_id", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("technicians", "telegram_chat_id")
