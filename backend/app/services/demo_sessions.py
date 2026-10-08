from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import DemoSession
from app.scripts.reset_demo import reset_demo_data

_LOCK_ID = 0x534F4C56


class DemoSessionUnauthorizedError(Exception):
    pass


@dataclass(frozen=True)
class DemoSessionOccupiedError(Exception):
    expires_at: datetime
    retry_after_seconds: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(session: DemoSession, token: str | None) -> bool:
    return bool(
        token and session.token_hash
        and hmac.compare_digest(token_hash(token), session.token_hash)
    )


def is_active(session: DemoSession, now: datetime) -> bool:
    current = aware(now)
    expires_at = aware(session.expires_at)
    return bool(session.token_hash and current and expires_at and expires_at > current)


def lock_state(db: Session) -> DemoSession:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _LOCK_ID})
    session = db.scalar(select(DemoSession).where(DemoSession.id == 1).with_for_update())
    if session is None:
        session = DemoSession(id=1, generation=0)
        db.add(session)
        db.flush()
    return session


def clear_state(session: DemoSession) -> None:
    session.token_hash = None
    session.created_at = None
    session.last_seen_at = None
    session.expires_at = None
    session.telegram_chat_id = None


def acquire(db: Session, settings: Settings, *, now: datetime | None = None) -> tuple[str, DemoSession]:
    current = aware(now or utc_now())
    assert current is not None
    try:
        session = lock_state(db)
        if is_active(session, current):
            expires_at = aware(session.expires_at)
            assert expires_at is not None
            raise DemoSessionOccupiedError(
                expires_at=expires_at,
                retry_after_seconds=max(1, int((expires_at - current).total_seconds())),
            )
        reset_demo_data(db)
        token = secrets.token_urlsafe(32)
        session.generation += 1
        session.token_hash = token_hash(token)
        session.created_at = current
        session.last_seen_at = current
        session.expires_at = current + timedelta(minutes=settings.solvo_demo_session_idle_minutes)
        session.telegram_chat_id = None
        db.commit()
        db.refresh(session)
        return token, session
    except DemoSessionOccupiedError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def require_active(
    db: Session, token: str | None, settings: Settings, *,
    now: datetime | None = None, lock: bool = False,
) -> DemoSession:
    if not settings.solvo_demo_session_enabled:
        raise DemoSessionUnauthorizedError("Sessione demo non disponibile.")
    current = aware(now or utc_now())
    assert current is not None
    session = lock_state(db) if lock else db.get(DemoSession, 1)
    if session is None or not is_active(session, current) or not token_matches(session, token):
        raise DemoSessionUnauthorizedError("Sessione demo non valida o scaduta.")
    return session


def require_generation(
    db: Session, generation: int, settings: Settings, *,
    now: datetime | None = None, lock: bool = False,
) -> DemoSession:
    if not settings.solvo_demo_session_enabled:
        raise DemoSessionUnauthorizedError("Sessione demo non disponibile.")
    current = aware(now or utc_now())
    assert current is not None
    session = lock_state(db) if lock else db.scalar(
        select(DemoSession)
        .where(DemoSession.id == 1)
        .execution_options(populate_existing=True)
    )
    if (
        session is None
        or not is_active(session, current)
        or session.generation != generation
    ):
        raise DemoSessionUnauthorizedError("Sessione demo non valida o scaduta.")
    return session


def active_generation(db: Session, settings: Settings) -> int | None:
    if not settings.solvo_demo_session_enabled:
        return None
    session = db.scalar(
        select(DemoSession)
        .where(DemoSession.id == 1)
        .execution_options(populate_existing=True)
    )
    if session is None or not is_active(session, utc_now()):
        return None
    return session.generation


def heartbeat(db: Session, token: str | None, settings: Settings, *, now: datetime | None = None) -> DemoSession:
    current = aware(now or utc_now())
    assert current is not None
    try:
        session = require_active(db, token, settings, now=current, lock=True)
        session.last_seen_at = current
        session.expires_at = current + timedelta(minutes=settings.solvo_demo_session_idle_minutes)
        db.commit()
        db.refresh(session)
        return session
    except Exception:
        db.rollback()
        raise


def release(db: Session, token: str | None, settings: Settings) -> None:
    try:
        session = require_active(db, token, settings, lock=True)
        reset_demo_data(db)
        clear_state(session)
        db.commit()
    except Exception:
        db.rollback()
        raise


def unlink_telegram(db: Session, token: str | None, settings: Settings) -> DemoSession:
    try:
        session = require_active(db, token, settings, lock=True)
        session.telegram_chat_id = None
        db.commit()
        db.refresh(session)
        return session
    except Exception:
        db.rollback()
        raise
