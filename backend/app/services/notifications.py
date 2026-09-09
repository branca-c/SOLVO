"""Technician notification port; destinations are owned by each adapter."""
from dataclasses import dataclass
import hashlib
import logging
import re
from typing import Protocol

import httpx

from app.core.config import Settings


class NotificationUnavailableError(Exception):
    pass


class _RedactBotURL(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(r'/bot[^/\s"?]+', '/bot[REDACTED]', record.getMessage())
        record.args = ()
        return True


# HTTPX logs request URLs at INFO, and HTTP Core logs request headers at DEBUG.
for _name in ('httpx', 'httpcore.http11', 'httpcore.http2'):
    logging.getLogger(_name).addFilter(_RedactBotURL())


@dataclass(frozen=True)
class Delivery:
    provider: str
    message_id: str
    status: str


class NotificationProvider(Protocol):
    def send(self, technician_id: int, message: str) -> Delivery: ...


class MockNotificationProvider:
    def send(self, technician_id: int, message: str) -> Delivery:
        digest = hashlib.sha256(f'{technician_id}\n{message}'.encode()).hexdigest()[:24]
        return Delivery('mock', f'mock-{digest}', 'simulated')


class TelegramNotificationProvider:
    def __init__(self, bot_token: str, demo_chat_id: str):
        self._bot_token = bot_token
        self._demo_chat_id = demo_chat_id

    def send(self, technician_id: int, message: str) -> Delivery:
        # Demo shortcut: all routed technicians share the configured destination.
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f'https://api.telegram.org/bot{self._bot_token}/sendMessage',
                    json={
                        'chat_id': self._demo_chat_id,
                        'text': message,
                        'link_preview_options': {'is_disabled': True},
                    },
                )
                response.raise_for_status()
                body = response.json()
                result = body.get('result') if isinstance(body, dict) else None
                if not isinstance(body, dict) or body.get('ok') is not True or not isinstance(result, dict):
                    raise ValueError('Invalid provider response')
                message_id = result.get('message_id')
                if type(message_id) is not int or message_id <= 0:
                    raise ValueError('Invalid message ID')
                return Delivery('telegram', str(message_id), 'submitted')
        except (httpx.HTTPError, ValueError):
            # Never propagate the request URL (which contains the bot credential).
            raise NotificationUnavailableError(
                'Invio Telegram non confermato. Verifica la chat prima di riprovare.'
            ) from None


def create_notification_provider(settings: Settings) -> NotificationProvider:
    name = settings.notification_provider.strip().casefold()
    if name == 'mock':
        return MockNotificationProvider()
    if name == 'telegram':
        token = settings.telegram_bot_token.get_secret_value().strip()
        chat_id = settings.telegram_demo_chat_id.strip()
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token) or not re.fullmatch(r'-?[1-9][0-9]*', chat_id):
            raise NotificationUnavailableError(
                'Configurazione Telegram incompleta o non valida: configura TELEGRAM_BOT_TOKEN e TELEGRAM_DEMO_CHAT_ID.'
            )
        return TelegramNotificationProvider(token, chat_id)
    raise NotificationUnavailableError('Provider notifiche non disponibile.')
