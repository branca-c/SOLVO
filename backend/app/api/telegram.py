from __future__ import annotations

import hmac
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import Technician
from app.services.notifications import NotificationUnavailableError, TelegramNotificationProvider
from app.services.telegram_binding import (
    InvalidTelegramBindingTokenError,
    TelegramBindingConfigurationError,
    confirmation_bot_token,
    create_binding_token,
    normalized_bot_username,
    validate_binding_token,
    webhook_secret,
)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
Database = Annotated[Session, Depends(get_db)]
Configuration = Annotated[Settings, Depends(get_settings)]

_START = re.compile(r"^/start(?:@([A-Za-z0-9_]{5,32}))?\s+([A-Za-z0-9_-]{1,64})\s*$")


def _configured(settings: Settings) -> str:
    normalized_bot_username(settings)
    create_binding_token(1, settings, now=1)
    confirmation_bot_token(settings)
    return webhook_secret(settings)


def _confirmation(settings: Settings, chat_id: str, text: str) -> None:
    try:
        TelegramNotificationProvider(confirmation_bot_token(settings)).send(
            technician_id=0, message=text, destination=chat_id
        )
    except (TelegramBindingConfigurationError, NotificationUnavailableError):
        pass


@router.post("/webhook")
def telegram_webhook(
    update: dict,
    db: Database,
    settings: Configuration,
    secret_header: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
):
    try:
        expected_secret = _configured(settings)
    except TelegramBindingConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if secret_header is None or not hmac.compare_digest(secret_header, expected_secret):
        raise HTTPException(status_code=403, detail="Webhook Telegram non autorizzato.")

    message = update.get("message")
    if not isinstance(message, dict):
        return {"ok": True}
    chat = message.get("chat")
    text = message.get("text")
    if not isinstance(chat, dict) or chat.get("type") != "private" or not isinstance(text, str):
        return {"ok": True}
    chat_id = chat.get("id")
    if type(chat_id) is not int or chat_id == 0:
        return {"ok": True}
    match = _START.fullmatch(text)
    if match is None:
        return {"ok": True}
    mentioned_username = match.group(1)
    if mentioned_username and mentioned_username.casefold() != normalized_bot_username(settings).casefold():
        return {"ok": True}

    destination = str(chat_id)
    try:
        technician_id = validate_binding_token(match.group(2), settings)
    except InvalidTelegramBindingTokenError:
        _confirmation(settings, destination, "SOLVO: link di collegamento non valido o scaduto.")
        return {"ok": True}

    technician = db.get(Technician, technician_id)
    if technician is None:
        _confirmation(settings, destination, "SOLVO: link di collegamento non valido o scaduto.")
        return {"ok": True}
    if technician.telegram_chat_id:
        if hmac.compare_digest(technician.telegram_chat_id, destination):
            message_text = (
                f"SOLVO: Telegram collegato correttamente al tecnico "
                f"{technician.first_name} {technician.last_name}."
            )
        else:
            message_text = "SOLVO: il collegamento non può essere completato."
        _confirmation(settings, destination, message_text)
        return {"ok": True}
    if db.scalar(select(Technician.id).where(Technician.telegram_chat_id == destination)) is not None:
        _confirmation(settings, destination, "SOLVO: il collegamento non può essere completato.")
        return {"ok": True}
    technician.telegram_chat_id = destination
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _confirmation(settings, destination, "SOLVO: il collegamento non può essere completato.")
        return {"ok": True}
    _confirmation(
        settings,
        destination,
        f"SOLVO: Telegram collegato correttamente al tecnico {technician.first_name} {technician.last_name}.",
    )
    return {"ok": True}
