from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AssignmentStatus

if TYPE_CHECKING:
    from app.models.technician import Technician
    from app.models.work_order import WorkOrder


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_assignments_attempt_number_positive"),
        UniqueConstraint(
            "work_order_id", "attempt_number", name="uq_assignments_work_order_attempt"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    technician_id: Mapped[int] = mapped_column(ForeignKey("technicians.id"), index=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", validate_strings=True),
        default=AssignmentStatus.PENDING,
        server_default=text("'PENDING'"),
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int]

    work_order: Mapped[WorkOrder] = relationship(back_populates="assignments")
    technician: Mapped[Technician] = relationship(back_populates="assignments")

