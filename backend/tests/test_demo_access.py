from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Technician
from app.services.assignment_links import sign_assignment
from tests.test_assignments_api import configure, start
from tests.test_work_orders_api import create


DEMO_KEY = "demo-access-test-key"


def enable_demo_access(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "solvo_demo_access_enabled", True)
    monkeypatch.setattr(settings, "solvo_demo_access_key", SecretStr(DEMO_KEY))
    return settings


def test_normal_api_requires_a_valid_demo_key(api, monkeypatch):
    client, _ = api
    enable_demo_access(monkeypatch)

    missing = client.get("/api/categories")
    invalid = client.get("/api/categories", headers={"X-SOLVO-DEMO-KEY": "wrong"})
    accepted = client.get("/api/categories", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY})

    assert missing.status_code == invalid.status_code == 401
    assert missing.json() == {"detail": "Accesso demo non autorizzato."}
    assert "DEMO" not in missing.text
    assert accepted.status_code == 200


def test_enabled_gate_with_no_configured_key_fails_closed(api, monkeypatch):
    client, _ = api
    settings = enable_demo_access(monkeypatch)
    monkeypatch.setattr(settings, "solvo_demo_access_key", SecretStr(""))

    response = client.get("/api/categories", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY})

    assert response.status_code == 401
    assert response.json() == {"detail": "Accesso demo non autorizzato."}


def test_health_remains_public(api, monkeypatch):
    client, _ = api
    enable_demo_access(monkeypatch)

    assert client.get("/health").json() == {"status": "ok"}


def test_cors_allows_the_demo_key_header(api, monkeypatch):
    client, _ = api
    enable_demo_access(monkeypatch)

    response = client.options(
        "/api/categories",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-SOLVO-DEMO-KEY",
        },
    )

    assert response.status_code == 200
    assert "x-solvo-demo-key" in response.headers["access-control-allow-headers"].lower()


def test_signed_technician_action_remains_independent(api, monkeypatch):
    client, engine = api
    configure(engine)
    order = create(client)
    assignment = start(client, order)
    settings = enable_demo_access(monkeypatch)
    token = sign_assignment(assignment["id"], settings)

    response = client.get(f"/api/public/assignments/{token}")

    assert response.status_code == 200


def test_telegram_webhook_remains_independent(api, monkeypatch):
    client, _ = api
    settings = enable_demo_access(monkeypatch)
    monkeypatch.setattr(settings, "telegram_bot_username", "SolvoTestBot")
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr("123456:test-token"))
    monkeypatch.setattr(settings, "telegram_binding_secret", SecretStr("binding-secret"))
    monkeypatch.setattr(settings, "telegram_webhook_secret", SecretStr("webhook-secret"))

    response = client.post(
        "/api/telegram/webhook", json={},
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_telegram_link_creation_is_operator_gated(api, monkeypatch):
    client, engine = api
    with Session(engine) as db:
        technician = Technician(
            first_name="Ada", last_name="Rossi", phone="123",
            category_id=1, escalation_order=1, is_team_leader=False,
        )
        db.add(technician)
        db.commit()
        technician_id = technician.id
    settings = enable_demo_access(monkeypatch)
    monkeypatch.setattr(settings, "telegram_bot_username", "SolvoTestBot")
    monkeypatch.setattr(settings, "telegram_binding_secret", SecretStr("binding-secret"))

    denied = client.post(f"/api/technicians/{technician_id}/telegram-link")
    accepted = client.post(
        f"/api/technicians/{technician_id}/telegram-link",
        headers={"X-SOLVO-DEMO-KEY": DEMO_KEY},
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200


def test_realtime_requires_first_frame_demo_key_when_enabled(api, monkeypatch):
    client, _ = api
    enable_demo_access(monkeypatch)

    with client.websocket_connect("/ws/work-orders") as socket:
        socket.send_text(DEMO_KEY)
        assert socket.receive_text() == "authorized"
