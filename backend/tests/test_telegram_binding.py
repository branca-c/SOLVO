from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Technician
from app.services.notifications import Delivery, TelegramNotificationProvider
from app.services.telegram_binding import (
    InvalidTelegramBindingTokenError,
    create_binding_token,
    validate_binding_token,
)


@pytest.fixture(autouse=True)
def telegram_binding_configuration(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_username", "@SolvoTestBot")
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr("123456:test-bot-token"))
    monkeypatch.setattr(settings, "telegram_binding_secret", SecretStr("binding-secret"))
    monkeypatch.setattr(settings, "telegram_webhook_secret", SecretStr("webhook-secret"))
    monkeypatch.setattr(settings, "telegram_binding_token_ttl_minutes", 15)
    return settings


@pytest.fixture(autouse=True)
def confirmation_is_local(monkeypatch):
    calls = []

    def send(self, technician_id, message, *, destination=None):
        calls.append((technician_id, message, destination))
        return Delivery("telegram", "1", "submitted")

    monkeypatch.setattr(TelegramNotificationProvider, "send", send)
    return calls


def _technicians(engine, count=1):
    with Session(engine) as db:
        technicians = [
            Technician(
                first_name=f"Tecnico{index}", last_name="Telegram", phone=f"{index}",
                category_id=1, escalation_order=index, is_team_leader=False,
            )
            for index in range(1, count + 1)
        ]
        db.add_all(technicians)
        db.flush()
        ids = [technician.id for technician in technicians]
        db.commit()
    return ids


def _webhook(client, payload, secret="webhook-secret"):
    return client.post(
        "/api/telegram/webhook", json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )


def _start_update(payload, chat_id=12345, username="SolvoTestBot"):
    return {
        "message": {
            "chat": {"id": chat_id, "type": "private"},
            "text": f"/start@{username} {payload}",
        }
    }


def test_binding_token_is_compact_signed_and_expires(telegram_binding_configuration, monkeypatch):
    payload, expires_at = create_binding_token(123456789, telegram_binding_configuration, now=1000)
    assert len(payload) <= 64
    assert expires_at == datetime.fromtimestamp(1900, UTC)
    assert validate_binding_token(payload, telegram_binding_configuration, now=1899) == 123456789
    with pytest.raises(InvalidTelegramBindingTokenError):
        validate_binding_token(payload[:-1] + "0", telegram_binding_configuration, now=1100)
    with pytest.raises(InvalidTelegramBindingTokenError):
        validate_binding_token(payload, telegram_binding_configuration, now=1901)
    monkeypatch.setattr(telegram_binding_configuration, "telegram_binding_secret", SecretStr("wrong-secret"))
    with pytest.raises(InvalidTelegramBindingTokenError):
        validate_binding_token(payload, telegram_binding_configuration, now=1100)


def test_link_endpoint_is_safe_and_does_not_bind(api):
    client, engine = api
    technician_id = _technicians(engine)[0]
    response = client.post(f"/api/technicians/{technician_id}/telegram-link")
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("https://t.me/SolvoTestBot?start=")
    assert body["telegram_linked"] is False
    assert "telegram_chat_id" not in body
    assert client.get("/api/technicians").json()[0]["telegram_linked"] is False


def test_link_endpoint_conflict_and_missing_configuration(api, monkeypatch, telegram_binding_configuration):
    client, engine = api
    technician_id = _technicians(engine)[0]
    with Session(engine) as db:
        db.get(Technician, technician_id).telegram_chat_id = "12345"
        db.commit()
    assert client.post(f"/api/technicians/{technician_id}/telegram-link").status_code == 409
    with Session(engine) as db:
        db.get(Technician, technician_id).telegram_chat_id = None
        db.commit()
    monkeypatch.setattr(telegram_binding_configuration, "telegram_binding_secret", SecretStr(""))
    assert client.post(f"/api/technicians/{technician_id}/telegram-link").status_code == 503


def test_webhook_auth_and_unrelated_updates_do_not_change_data(api):
    client, engine = api
    technician_id = _technicians(engine)[0]
    update = {"message": {"chat": {"id": 12345, "type": "private"}, "text": "ciao"}}
    assert client.post("/api/telegram/webhook", json=update).status_code == 403
    assert _webhook(client, update, secret="wrong-secret").status_code == 403
    assert _webhook(client, update).status_code == 200
    assert client.get("/api/technicians").json()[0]["telegram_linked"] is False
    assert technician_id > 0


def test_webhook_binds_safely_and_public_api_hides_chat_id(api, telegram_binding_configuration):
    client, engine = api
    technician_id = _technicians(engine)[0]
    payload, _ = create_binding_token(technician_id, telegram_binding_configuration)
    assert _webhook(client, _start_update(payload)).status_code == 200
    technicians = client.get("/api/technicians").json()
    assert technicians[0]["telegram_linked"] is True
    assert "telegram_chat_id" not in technicians[0]
    assert _webhook(client, _start_update(payload)).status_code == 200
    with Session(engine) as db:
        assert db.get(Technician, technician_id).telegram_chat_id == "12345"
    assert _webhook(client, _start_update(payload, chat_id=67890)).status_code == 200
    with Session(engine) as db:
        assert db.get(Technician, technician_id).telegram_chat_id == "12345"


def test_webhook_rejects_chat_reuse_and_invalid_tokens(api, telegram_binding_configuration):
    client, engine = api
    first_id, second_id = _technicians(engine, count=2)
    first_token, _ = create_binding_token(first_id, telegram_binding_configuration)
    second_token, _ = create_binding_token(second_id, telegram_binding_configuration)
    assert _webhook(client, _start_update(first_token, chat_id=12345)).status_code == 200
    assert _webhook(client, _start_update(second_token, chat_id=12345)).status_code == 200
    assert _webhook(client, _start_update(second_token[:-1] + "0", chat_id=67890)).status_code == 200
    expired, _ = create_binding_token(second_id, telegram_binding_configuration, now=1)
    assert _webhook(client, _start_update(expired, chat_id=67890)).status_code == 200
    with Session(engine) as db:
        assert db.get(Technician, first_id).telegram_chat_id == "12345"
        assert db.get(Technician, second_id).telegram_chat_id is None


def test_unlink_is_idempotent_and_never_returns_chat_id(api):
    client, engine = api
    technician_id = _technicians(engine)[0]
    with Session(engine) as db:
        db.get(Technician, technician_id).telegram_chat_id = "12345"
        db.commit()
    response = client.delete(f"/api/technicians/{technician_id}/telegram-link")
    assert response.status_code == 200
    assert response.json() == {"telegram_linked": False}
    assert client.delete(f"/api/technicians/{technician_id}/telegram-link").json() == {
        "telegram_linked": False
    }
