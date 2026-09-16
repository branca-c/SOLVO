"""Require textual reminders, preserving legacy records without inventing content.

Revision ID: 20260916_0003
Revises: 20260916_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260916_0003"
down_revision = "20260916_0002"
branch_labels = None
depends_on = None
LEGACY_TEXT = "Sollecito precedente: testo non disponibile."


def upgrade() -> None:
    op.add_column("reminders", sa.Column("text", sa.Text(), nullable=True))
    reminders = sa.table("reminders", sa.column("text", sa.Text()))
    op.execute(reminders.update().where(reminders.c.text.is_(None)).values(text=LEGACY_TEXT))
    with op.batch_alter_table("reminders") as batch:
        batch.alter_column("text", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("text")
