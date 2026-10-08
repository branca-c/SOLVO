from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DemoSession(Base):
    __tablename__ = "demo_sessions"
    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_sessions_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
