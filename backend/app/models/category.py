from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.technician import Technician
    from app.models.work_order import WorkOrder


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    technicians: Mapped[list[Technician]] = relationship(back_populates="category")
    work_orders: Mapped[list[WorkOrder]] = relationship(back_populates="category")

