"""Require unique private Telegram destinations.

Revision ID: 20260930_0005
Revises: 20260930_0004
Create Date: 2026-09-30
"""

from alembic import op


revision = "20260930_0005"
down_revision = "20260930_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_technicians_telegram_chat_id", "technicians", ["telegram_chat_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_technicians_telegram_chat_id", "technicians", type_="unique")
