from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Priority, WorkOrderStatus

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.category import Category
    from app.models.reminder import Reminder
    from app.models.work_order_history import WorkOrderHistory


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint("reminders_count >= 0", name="ck_work_orders_reminders_count_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user_first_name: Mapped[str] = mapped_column(String(100))
    user_last_name: Mapped[str] = mapped_column(String(100))
    user_phone: Mapped[str] = mapped_column(String(32))
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fault_address: Mapped[str] = mapped_column(String(500))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority", validate_strings=True)
    )
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status", validate_strings=True),
        default=WorkOrderStatus.APERTO,
        server_default=text("'APERTO'"),
    )
    reminders_count: Mapped[int] = mapped_column(default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="work_orders")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    reminders: Mapped[list[Reminder]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )
    history: Mapped[list[WorkOrderHistory]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )

