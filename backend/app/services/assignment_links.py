"""Scoped, expiring bearer links. No tokens or secrets are stored in the database."""
import hashlib
import hmac
import re
import time
from urllib.parse import urlsplit

from app.core.config import Settings


class ActionLinkConfigurationError(Exception):
    pass


class InvalidActionTokenError(Exception):
    pass


def _key(settings: Settings) -> bytes:
    key = settings.assignment_action_secret.get_secret_value()
    if len(key.encode()) < 32 or key.startswith('replace-'):
        raise ActionLinkConfigurationError('Configura ASSIGNMENT_ACTION_SECRET con un segreto casuale di almeno 32 byte.')
    return key.encode()


def _signature(payload: str, key: bytes) -> str:
    return hmac.new(key, f'solvo:assignment-action:{payload}'.encode(), hashlib.sha256).hexdigest()


def sign_assignment(assignment_id: int, settings: Settings, *, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    payload = f'v1.{assignment_id}.{issued + settings.technician_action_token_ttl_minutes * 60}'
    return f'{payload}.{_signature(payload, _key(settings))}'


def validate_token(token: str, settings: Settings, *, now: int | None = None) -> int:
    key = _key(settings)
    if not re.fullmatch(r'v1\.[1-9][0-9]{0,18}\.[0-9]{1,12}\.[0-9a-f]{64}', token):
        raise InvalidActionTokenError('Link non valido o scaduto.')
    payload, signature = token.rsplit('.', 1)
    if not hmac.compare_digest(signature, _signature(payload, key)):
        raise InvalidActionTokenError('Link non valido o scaduto.')
    _, assignment_id, expires = payload.split('.')
    if int(expires) <= (int(time.time()) if now is None else now):
        raise InvalidActionTokenError('Link non valido o scaduto.')
    return int(assignment_id)


def action_url(assignment_id: int, settings: Settings) -> str:
    base = settings.technician_action_base_url.rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ActionLinkConfigurationError('TECHNICIAN_ACTION_BASE_URL deve essere un URL HTTP(S) senza credenziali, query o frammento.')
    return f'{base}/tecnico/assegnazione/{sign_assignment(assignment_id, settings)}'
