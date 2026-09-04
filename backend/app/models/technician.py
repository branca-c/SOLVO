from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.category import Category


class Technician(Base):
    __tablename__ = "technicians"
    __table_args__ = (
        CheckConstraint("escalation_order > 0", name="ck_technicians_escalation_order_positive"),
        UniqueConstraint(
            "category_id",
            "escalation_order",
            name="uq_technicians_category_escalation_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    escalation_order: Mapped[int]
    is_team_leader: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    category: Mapped[Category] = relationship(back_populates="technicians")
    assignments: Mapped[list[Assignment]] = relationship(back_populates="technician")

