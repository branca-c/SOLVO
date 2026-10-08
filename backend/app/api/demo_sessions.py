from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.demo_access import DEMO_SESSION_HEADER
from app.db.session import get_db
from app.schemas.demo_session import DemoSessionResponse, DemoSessionStatusResponse
from app.schemas.telegram_binding import TelegramBindingLinkResponse, TelegramBindingStatusResponse
from app.services import demo_sessions
from app.services.telegram_binding import TelegramBindingConfigurationError, demo_binding_url

router = APIRouter(prefix="/api/demo-session", tags=["demo-session"])
Database = Annotated[Session, Depends(get_db)]
Configuration = Annotated[Settings, Depends(get_settings)]
SessionToken = Annotated[str | None, Header(alias=DEMO_SESSION_HEADER)]


def _unauthorized(exc: Exception) -> HTTPException:
    return HTTPException(401, detail=str(exc), headers={"Cache-Control": "no-store"})


@router.post("/acquire", response_model=DemoSessionResponse)
def acquire_demo_session(db: Database, settings: Configuration, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not settings.solvo_demo_session_enabled:
        return DemoSessionResponse(enabled=False)
    try:
        token, session = demo_sessions.acquire(db, settings)
    except demo_sessions.DemoSessionOccupiedError as exc:
        raise HTTPException(
            409,
            detail={
                "code": "DEMO_IN_USE",
                "message": "Demo temporaneamente in uso.",
                "retry_after_seconds": exc.retry_after_seconds,
                "expires_at": exc.expires_at.isoformat(),
            },
            headers={"Cache-Control": "no-store", "Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return DemoSessionResponse(
        session_token=token, expires_at=session.expires_at,
        telegram_linked=bool(session.telegram_chat_id),
    )


@router.get("", response_model=DemoSessionStatusResponse)
def demo_session_status(db: Database, settings: Configuration, session_token: SessionToken):
    if not settings.solvo_demo_session_enabled:
        return DemoSessionStatusResponse(enabled=False)
    try:
        session = demo_sessions.require_active(db, session_token, settings)
    except demo_sessions.DemoSessionUnauthorizedError as exc:
        raise _unauthorized(exc) from exc
    return DemoSessionStatusResponse(
        expires_at=session.expires_at, telegram_linked=bool(session.telegram_chat_id)
    )


@router.post("/heartbeat", response_model=DemoSessionStatusResponse)
def heartbeat(db: Database, settings: Configuration, session_token: SessionToken):
    if not settings.solvo_demo_session_enabled:
        return DemoSessionStatusResponse(enabled=False)
    try:
        session = demo_sessions.heartbeat(db, session_token, settings)
    except demo_sessions.DemoSessionUnauthorizedError as exc:
        raise _unauthorized(exc) from exc
    return DemoSessionStatusResponse(
        expires_at=session.expires_at, telegram_linked=bool(session.telegram_chat_id)
    )


@router.delete("", status_code=204)
def release(db: Database, settings: Configuration, session_token: SessionToken):
    if not settings.solvo_demo_session_enabled:
        return Response(status_code=204)
    try:
        demo_sessions.release(db, session_token, settings)
    except demo_sessions.DemoSessionUnauthorizedError as exc:
        raise _unauthorized(exc) from exc
    return Response(status_code=204)


@router.post("/telegram-link", response_model=TelegramBindingLinkResponse)
def create_telegram_link(db: Database, settings: Configuration, session_token: SessionToken):
    try:
        session = demo_sessions.require_active(db, session_token, settings)
        if session.telegram_chat_id:
            raise HTTPException(409, detail="Telegram è già collegato alla sessione demo.")
        url, expires_at = demo_binding_url(session.generation, settings)
    except demo_sessions.DemoSessionUnauthorizedError as exc:
        raise _unauthorized(exc) from exc
    except TelegramBindingConfigurationError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return TelegramBindingLinkResponse(url=url, expires_at=expires_at, telegram_linked=False)


@router.delete("/telegram-link", response_model=TelegramBindingStatusResponse)
def delete_telegram_link(db: Database, settings: Configuration, session_token: SessionToken):
    try:
        demo_sessions.unlink_telegram(db, session_token, settings)
    except demo_sessions.DemoSessionUnauthorizedError as exc:
        raise _unauthorized(exc) from exc
    return TelegramBindingStatusResponse(telegram_linked=False)
