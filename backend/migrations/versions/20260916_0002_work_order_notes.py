"""Add separate WorkOrder notes.
Revision ID: 20260916_0002
Revises: 20260904_0001
"""
from alembic import op
import sqlalchemy as sa
revision = "20260916_0002"
down_revision = "20260904_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("work_order_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_work_order_notes_work_order_id", "work_order_notes", ["work_order_id"])

def downgrade() -> None:
    op.drop_index("ix_work_order_notes_work_order_id", table_name="work_order_notes")
    op.drop_table("work_order_notes")
