"""Create SOLVO MVP domain models.

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("UTENTE", "OPERATORE", "TECNICO", name="user_role", create_type=False)
priority = postgresql.ENUM(
    "PROGRAMMABILE", "BASSA", "MEDIA", "ALTA", "URGENTE", name="priority", create_type=False
)
work_order_status = postgresql.ENUM(
    "APERTO", "IN_CORSO", "EVASO", "CHIUSO", "ANNULLATO",
    name="work_order_status",
    create_type=False,
)
assignment_status = postgresql.ENUM(
    "PENDING", "ACCEPTED", "REJECTED", "NO_RESPONSE", "ESCALATED",
    name="assignment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    priority.create(bind, checkfirst=True)
    work_order_status.create(bind, checkfirst=True)
    assignment_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "technicians",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("escalation_order", sa.Integer(), nullable=False),
        sa.Column("is_team_leader", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "escalation_order > 0", name="ck_technicians_escalation_order_positive"
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_id", "escalation_order", name="uq_technicians_category_escalation_order"
        ),
    )
    op.create_index("ix_technicians_category_id", "technicians", ["category_id"])
    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_first_name", sa.String(length=100), nullable=False),
        sa.Column("user_last_name", sa.String(length=100), nullable=False),
        sa.Column("user_phone", sa.String(length=32), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("fault_address", sa.String(length=500), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status", work_order_status, server_default=sa.text("'APERTO'"), nullable=False
        ),
        sa.Column("reminders_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "reminders_count >= 0", name="ck_work_orders_reminders_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_orders_category_id", "work_orders", ["category_id"])
    op.create_index("ix_work_orders_code", "work_orders", ["code"], unique=True)
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", assignment_status, server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_notes", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempt_number > 0", name="ck_assignments_attempt_number_positive"),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_order_id", "attempt_number", name="uq_assignments_work_order_attempt"
        ),
    )
    op.create_index("ix_assignments_technician_id", "assignments", ["technician_id"])
    op.create_index("ix_assignments_work_order_id", "assignments", ["work_order_id"])
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_created_by", "reminders", ["created_by"])
    op.create_index("ix_reminders_work_order_id", "reminders", ["work_order_id"])
    op.create_table(
        "work_order_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_order_history_work_order_id", "work_order_history", ["work_order_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_work_order_history_work_order_id", table_name="work_order_history")
    op.drop_table("work_order_history")
    op.drop_index("ix_reminders_work_order_id", table_name="reminders")
    op.drop_index("ix_reminders_created_by", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("ix_assignments_work_order_id", table_name="assignments")
    op.drop_index("ix_assignments_technician_id", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("ix_work_orders_code", table_name="work_orders")
    op.drop_index("ix_work_orders_category_id", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("ix_technicians_category_id", table_name="technicians")
    op.drop_table("technicians")
    op.drop_table("categories")
    op.drop_table("users")

    bind = op.get_bind()
    assignment_status.drop(bind, checkfirst=True)
    work_order_status.drop(bind, checkfirst=True)
    priority.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)

