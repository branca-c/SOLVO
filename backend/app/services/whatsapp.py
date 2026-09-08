"""WhatsApp delivery port. Mock never constructs an HTTP client."""
from dataclasses import dataclass
import hashlib
import re
from typing import Protocol

import httpx

from app.core.config import Settings


class NotificationUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class Delivery:
    provider: str
    message_id: str
    status: str


class WhatsAppProvider(Protocol):
    def send(self, phone: str, message: str) -> Delivery: ...


def whatsapp_address(phone: str) -> str:
    number = phone.removeprefix('whatsapp:')
    if not re.fullmatch(r'\+[1-9][0-9]{5,14}', number):
        raise NotificationUnavailableError('Configura il numero WhatsApp in formato internazionale +... .')
    return f'whatsapp:{number}'


class MockWhatsAppProvider:
    def send(self, phone: str, message: str) -> Delivery:
        recipient = whatsapp_address(phone)
        digest = hashlib.sha256(f'{recipient}\n{message}'.encode()).hexdigest()[:24]
        return Delivery('mock', f'mock-{digest}', 'simulated')


class TwilioWhatsAppProvider:
    def __init__(self, sid: str, auth_token: str, sender: str):
        self.sid = sid
        self.auth_token = auth_token
        self.sender = whatsapp_address(sender)

    def send(self, phone: str, message: str) -> Delivery:
        recipient = whatsapp_address(phone)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f'https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json',
                    auth=(self.sid, self.auth_token),
                    data={'From': self.sender, 'To': recipient, 'Body': message},
                )
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or not re.fullmatch(r'SM[0-9a-fA-F]{32}', str(result.get('sid', ''))):
                    raise ValueError('Invalid provider response')
                if result.get('status') not in {'accepted', 'scheduled', 'queued', 'sending', 'sent', 'delivered', 'read'}:
                    raise ValueError('Provider rejected the message')
                return Delivery('twilio', result['sid'], 'submitted')
        except (httpx.HTTPError, ValueError) as exc:
            raise NotificationUnavailableError('Invio WhatsApp non confermato. Verifica la console Twilio prima di riprovare.') from exc


def create_whatsapp_provider(settings: Settings) -> WhatsAppProvider:
    name = settings.whatsapp_provider.strip().casefold()
    if name == 'mock':
        return MockWhatsAppProvider()
    if name == 'twilio':
        sid = settings.twilio_account_sid
        token = settings.twilio_auth_token.get_secret_value()
        if not re.fullmatch(r'AC[0-9a-fA-F]{32}', sid) or not token or not settings.twilio_whatsapp_from:
            raise NotificationUnavailableError('Configurazione Twilio incompleta o non valida.')
        return TwilioWhatsAppProvider(sid, token, settings.twilio_whatsapp_from)
    raise NotificationUnavailableError('Provider WhatsApp non disponibile.')
