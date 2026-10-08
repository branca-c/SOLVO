"""Private Telegram deep-link binding, isolated from assignment action links."""

from __future__ import annotations

from datetime import UTC, datetime
import base64
import hashlib
import hmac
import re
import time

from app.core.config import Settings


class TelegramBindingConfigurationError(Exception):
    pass


class InvalidTelegramBindingTokenError(Exception):
    pass


_PAYLOAD_PATTERN = re.compile(r"b1_([0-9a-z]+)_([0-9a-z]+)_([0-9a-f]{32})")
_DEMO_PAYLOAD_PATTERN = re.compile(r"d1_([0-9a-z]+)_([0-9a-z]+)_([0-9a-f]{32})")
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{5,32}")


def normalized_bot_username(settings: Settings) -> str:
    username = settings.telegram_bot_username.strip().removeprefix("@").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise TelegramBindingConfigurationError(
            "Configurazione collegamento Telegram non disponibile."
        )
    return username


def _secret(settings: Settings) -> bytes:
    secret = settings.telegram_binding_secret.get_secret_value().strip()
    if not secret:
        raise TelegramBindingConfigurationError(
            "Configurazione collegamento Telegram non disponibile."
        )
    return secret.encode()


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value <= 0:
        raise ValueError("expected positive integer")
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


def _from_base36(value: str) -> int:
    try:
        parsed = int(value, 36)
    except ValueError as exc:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.") from exc
    if parsed <= 0 or _base36(parsed) != value:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    return parsed


def _signature(technician_id: int, expires_at: int, secret: bytes) -> str:
    signed = f"b1:{technician_id}:{expires_at}".encode()
    return hmac.new(secret, signed, hashlib.sha256).hexdigest()[:32]


def _demo_signature(generation: int, expires_at: int, secret: bytes) -> str:
    signed = f"d1:{generation}:{expires_at}".encode()
    return hmac.new(secret, signed, hashlib.sha256).hexdigest()[:32]


def create_binding_token(
    technician_id: int, settings: Settings, *, now: int | None = None
) -> tuple[str, datetime]:
    secret = _secret(settings)
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + settings.telegram_binding_token_ttl_minutes * 60
    payload = f"b1_{_base36(technician_id)}_{_base36(expires_at)}_{_signature(technician_id, expires_at, secret)}"
    if len(payload) > 64:
        raise TelegramBindingConfigurationError("Configurazione collegamento Telegram non disponibile.")
    return payload, datetime.fromtimestamp(expires_at, UTC)


def validate_binding_token(payload: str, settings: Settings, *, now: int | None = None) -> int:
    match = _PAYLOAD_PATTERN.fullmatch(payload)
    if match is None:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    technician_id = _from_base36(match.group(1))
    expires_at = _from_base36(match.group(2))
    expected = _signature(technician_id, expires_at, _secret(settings))
    if not hmac.compare_digest(match.group(3), expected):
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    current_time = int(time.time()) if now is None else now
    if expires_at < current_time:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    return technician_id


def binding_url(technician_id: int, settings: Settings) -> tuple[str, datetime]:
    username = normalized_bot_username(settings)
    payload, expires_at = create_binding_token(technician_id, settings)
    return f"https://t.me/{username}?start={payload}", expires_at


def create_demo_binding_token(
    generation: int, settings: Settings, *, now: int | None = None
) -> tuple[str, datetime]:
    secret = _secret(settings)
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + settings.telegram_binding_token_ttl_minutes * 60
    payload = (
        f"d1_{_base36(generation)}_{_base36(expires_at)}_"
        f"{_demo_signature(generation, expires_at, secret)}"
    )
    if len(payload) > 64:
        raise TelegramBindingConfigurationError("Configurazione collegamento Telegram non disponibile.")
    return payload, datetime.fromtimestamp(expires_at, UTC)


def validate_demo_binding_token(
    payload: str, settings: Settings, *, now: int | None = None
) -> int:
    match = _DEMO_PAYLOAD_PATTERN.fullmatch(payload)
    if match is None:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    generation = _from_base36(match.group(1))
    expires_at = _from_base36(match.group(2))
    expected = _demo_signature(generation, expires_at, _secret(settings))
    if not hmac.compare_digest(match.group(3), expected):
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    current_time = int(time.time()) if now is None else now
    if expires_at < current_time:
        raise InvalidTelegramBindingTokenError("Token non valido o scaduto.")
    return generation


def demo_binding_url(generation: int, settings: Settings) -> tuple[str, datetime]:
    username = normalized_bot_username(settings)
    payload, expires_at = create_demo_binding_token(generation, settings)
    return f"https://t.me/{username}?start={payload}", expires_at


def webhook_secret(settings: Settings) -> str:
    secret = settings.telegram_webhook_secret.get_secret_value().strip()
    if not secret:
        raise TelegramBindingConfigurationError(
            "Configurazione webhook Telegram non disponibile."
        )
    return secret


def confirmation_bot_token(settings: Settings) -> str:
    token = settings.telegram_bot_token.get_secret_value().strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise TelegramBindingConfigurationError(
            "Configurazione collegamento Telegram non disponibile."
        )
    return token
