from datetime import UTC, datetime, timedelta
from threading import Event, Thread

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.models import DemoSession, Technician, WorkOrder
from app import main as main_module
from app.services import demo_sessions
from app.services.notifications import Delivery, TelegramNotificationProvider
from app.services.telegram_binding import create_demo_binding_token

DEMO_KEY = "demo-session-test-key"


@pytest.fixture
def enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "solvo_demo_access_enabled", True)
    monkeypatch.setattr(settings, "solvo_demo_access_key", SecretStr(DEMO_KEY))
    monkeypatch.setattr(settings, "solvo_demo_session_enabled", True)
    monkeypatch.setattr(settings, "solvo_demo_session_idle_minutes", 10)
    monkeypatch.setattr(settings, "telegram_bot_username", "SolvoTestBot")
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr("123456:test-token"))
    monkeypatch.setattr(settings, "telegram_binding_secret", SecretStr("binding-secret"))
    monkeypatch.setattr(settings, "telegram_webhook_secret", SecretStr("webhook-secret"))
    monkeypatch.setattr(settings, "assignment_action_secret", SecretStr("assignment-secret-" * 3))
    return settings


def acquire(client):
    response = client.post(
        "/api/demo-session/acquire", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY}
    )
    assert response.status_code == 200, response.text
    return response.json()


def headers(token):
    return {"X-SOLVO-DEMO-KEY": DEMO_KEY, "X-SOLVO-DEMO-SESSION": token}


def test_acquire_stores_only_hash_and_second_visitor_gets_structured_conflict(api, enabled):
    client, engine = api
    first = acquire(client)
    assert first["enabled"] is True
    assert first["session_token"]
    assert first["telegram_linked"] is False
    with Session(engine) as db:
        stored = db.get(DemoSession, 1)
        assert stored.token_hash == demo_sessions.token_hash(first["session_token"])
        assert first["session_token"] not in stored.token_hash

    conflict = client.post(
        "/api/demo-session/acquire", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY}
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "DEMO_IN_USE"
    assert conflict.json()["detail"]["retry_after_seconds"] > 0
    assert "retry-after" in conflict.headers


def test_acquire_requires_the_demo_key_and_normal_apis_require_session(api, enabled):
    client, _ = api
    assert client.post("/api/demo-session/acquire").status_code == 401
    assert client.post(
        "/api/demo-session/acquire", headers={"X-SOLVO-DEMO-KEY": "wrong"}
    ).status_code == 401
    assert client.get(
        "/api/categories", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY}
    ).status_code == 401
    token = acquire(client)["session_token"]
    assert client.get("/api/categories", headers=headers(token)).status_code == 200


def test_expired_session_is_cleaned_and_reacquired(api, enabled, monkeypatch):
    client, engine = api
    first = acquire(client)
    with Session(engine) as db:
        db.add(WorkOrder(
            code="SOLVO-EXPIRED", user_first_name="A", user_last_name="B", user_phone="1",
            fault_address="Via Test", category_id=1, priority="MEDIA", description="Runtime",
        ))
        session = db.get(DemoSession, 1)
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    second = acquire(client)
    assert second["session_token"] != first["session_token"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == 0


def test_heartbeat_renews_and_wrong_token_is_rejected(api, enabled, monkeypatch):
    client, engine = api
    acquired = acquire(client)
    token = acquired["session_token"]
    before = datetime.fromisoformat(acquired["expires_at"])
    later = before - timedelta(minutes=5)
    monkeypatch.setattr(demo_sessions, "utc_now", lambda: later)
    renewed = client.post("/api/demo-session/heartbeat", headers=headers(token))
    assert renewed.status_code == 200
    assert datetime.fromisoformat(renewed.json()["expires_at"]) > before
    assert client.get("/api/categories", headers=headers("wrong-token")).status_code == 401
    with Session(engine) as db:
        assert db.get(DemoSession, 1).last_seen_at is not None


def test_release_cleans_runtime_preserves_technician_binding_and_allows_next(api, enabled):
    client, engine = api
    acquired = acquire(client)
    token = acquired["session_token"]
    with Session(engine) as db:
        technician = db.scalar(select(Technician).order_by(Technician.id))
        technician.telegram_chat_id = "permanent-tech-chat"
        db.add(WorkOrder(
            code="SOLVO-RELEASE", user_first_name="A", user_last_name="B", user_phone="1",
            fault_address="Via Test", category_id=1, priority="MEDIA", description="Runtime",
        ))
        technician_id = technician.id
        db.commit()
    assert client.delete("/api/demo-session", headers=headers(token)).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == 0
        assert db.get(Technician, technician_id).telegram_chat_id == "permanent-tech-chat"
        assert db.get(DemoSession, 1).token_hash is None
    assert acquire(client)["session_token"]


def test_release_rolls_back_cleanup_on_failure(api, enabled, monkeypatch):
    client, engine = api
    token = acquire(client)["session_token"]
    with Session(engine) as db:
        db.add(WorkOrder(
            code="SOLVO-ROLLBACK", user_first_name="A", user_last_name="B", user_phone="1",
            fault_address="Via Test", category_id=1, priority="MEDIA", description="Runtime",
        ))
        db.commit()

    def fail_after_delete(db, **_):
        db.execute(delete(WorkOrder))
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(demo_sessions, "reset_demo_data", fail_after_delete)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        client.delete("/api/demo-session", headers=headers(token))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == 1
        assert db.get(DemoSession, 1).token_hash is not None


def test_demo_telegram_binding_hides_chat_and_stale_generation_cannot_bind(api, enabled, monkeypatch):
    client, engine = api
    monkeypatch.setattr(
        TelegramNotificationProvider, "send",
        lambda self, technician_id, message, *, destination=None: Delivery("telegram", "1", "submitted"),
    )
    acquired = acquire(client)
    token = acquired["session_token"]
    link = client.post("/api/demo-session/telegram-link", headers=headers(token))
    assert link.status_code == 200
    assert "telegram_chat_id" not in link.text
    payload = link.json()["url"].split("start=", 1)[1]
    update = {"message": {"chat": {"id": 12345, "type": "private"}, "text": f"/start {payload}"}}
    webhook_headers = {"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"}
    assert client.post("/api/telegram/webhook", json=update, headers=webhook_headers).status_code == 200
    status = client.get("/api/demo-session", headers=headers(token))
    assert status.json()["telegram_linked"] is True
    assert "12345" not in status.text

    stale, _ = create_demo_binding_token(1, enabled)
    assert client.delete("/api/demo-session", headers=headers(token)).status_code == 204
    new = acquire(client)
    stale_update = {"message": {"chat": {"id": 67890, "type": "private"}, "text": f"/start {stale}"}}
    assert client.post("/api/telegram/webhook", json=stale_update, headers=webhook_headers).status_code == 200
    with Session(engine) as db:
        assert db.get(DemoSession, 1).telegram_chat_id is None
    assert new["telegram_linked"] is False


def test_session_telegram_can_be_unlinked_without_releasing_session(api, enabled):
    client, engine = api
    token = acquire(client)["session_token"]
    with Session(engine) as db:
        db.get(DemoSession, 1).telegram_chat_id = "session-chat"
        db.commit()
    response = client.delete("/api/demo-session/telegram-link", headers=headers(token))
    assert response.status_code == 200
    assert response.json() == {"telegram_linked": False}
    assert client.get("/api/categories", headers=headers(token)).status_code == 200


def test_session_telegram_overrides_real_routed_technician_destination(api, enabled, monkeypatch):
    client, engine = api
    token = acquire(client)["session_token"]
    with Session(engine) as db:
        session = db.get(DemoSession, 1)
        session.telegram_chat_id = "session-chat"
        technician = db.scalar(select(Technician).where(Technician.category_id == 1))
        technician.telegram_chat_id = "technician-chat"
        technician_id = technician.id
        db.commit()
    created = client.post("/api/work-orders", headers=headers(token), json={
        "user_first_name": "Demo", "user_last_name": "Sessione", "user_phone": "1",
        "fault_address": "Via Test", "category_id": 1, "priority": "MEDIA",
        "description": "Test notifica",
    }).json()
    assignment = client.post(
        f"/api/work-orders/{created['id']}/assignments/start", headers=headers(token)
    ).json()
    monkeypatch.setattr(enabled, "notification_provider", "telegram")
    destinations = []
    monkeypatch.setattr(
        TelegramNotificationProvider, "send",
        lambda self, technician_id, message, *, destination=None:
            destinations.append(destination) or Delivery("telegram", "1", "submitted"),
    )
    response = client.post(
        f"/api/assignments/{assignment['id']}/notify", headers=headers(token)
    )
    assert response.status_code == 200
    assert destinations == ["session-chat"]
    assert assignment["technician_id"] == technician_id


def test_stale_validated_request_cannot_write_after_release_and_reacquire(
    api, enabled, monkeypatch,
):
    client, engine = api
    first = acquire(client)
    validated = Event()
    resume = Event()
    original_require_active = main_module.require_active

    def pause_after_validation(db, token, settings):
        session = original_require_active(db, token, settings)
        if not validated.is_set():
            validated.set()
            assert resume.wait(timeout=5)
        return session

    monkeypatch.setattr(main_module, "require_active", pause_after_validation)
    result = {}

    def create_from_stale_session():
        result["response"] = client.post(
            "/api/work-orders", headers=headers(first["session_token"]), json={
                "user_first_name": "Sessione", "user_last_name": "Vecchia",
                "user_phone": "1", "fault_address": "Via Test",
                "category_id": 1, "priority": "MEDIA",
                "description": "Non deve entrare nella sessione successiva",
            },
        )

    from fastapi.testclient import TestClient

    with TestClient(client.app) as lifecycle_client:
        worker = Thread(target=create_from_stale_session, name="stale-demo-operation")
        worker.start()
        assert validated.wait(timeout=5)
        try:
            assert lifecycle_client.delete(
                "/api/demo-session", headers=headers(first["session_token"])
            ).status_code == 204
            second = acquire(lifecycle_client)
        finally:
            resume.set()
            worker.join(timeout=5)

    assert not worker.is_alive()
    assert result["response"].status_code == 401
    assert second["session_token"] != first["session_token"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == 0


def test_notification_started_by_old_generation_never_targets_new_session(
    api, enabled, monkeypatch,
):
    client, engine = api
    first = acquire(client)
    first_token = first["session_token"]
    with Session(engine) as db:
        db.get(DemoSession, 1).telegram_chat_id = "session-a-chat"
        db.commit()
    created = client.post("/api/work-orders", headers=headers(first_token), json={
        "user_first_name": "Demo", "user_last_name": "Sessione", "user_phone": "1",
        "fault_address": "Via Test", "category_id": 1, "priority": "MEDIA",
        "description": "Notifica generation-aware",
    }).json()
    assignment = client.post(
        f"/api/work-orders/{created['id']}/assignments/start", headers=headers(first_token)
    ).json()
    monkeypatch.setattr(enabled, "notification_provider", "telegram")
    sending = Event()
    resume = Event()
    destinations = []

    def paused_send(self, technician_id, message, *, destination=None):
        destinations.append(destination)
        sending.set()
        assert resume.wait(timeout=5)
        return Delivery("telegram", "1", "submitted")

    monkeypatch.setattr(TelegramNotificationProvider, "send", paused_send)
    result = {}

    def notify_from_first_session():
        result["response"] = client.post(
            f"/api/assignments/{assignment['id']}/notify", headers=headers(first_token)
        )

    worker = Thread(target=notify_from_first_session, name="stale-demo-notification")
    worker.start()
    assert sending.wait(timeout=5)
    try:
        # This succeeding while send() is paused also proves the advisory lock
        # is not retained across provider I/O.
        assert client.delete(
            "/api/demo-session", headers=headers(first_token)
        ).status_code == 204
        second = acquire(client)
        with Session(engine) as db:
            db.get(DemoSession, 1).telegram_chat_id = "session-b-chat"
            db.commit()
    finally:
        resume.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert second["session_token"] != first_token
    assert destinations == ["session-a-chat"]
    assert result["response"].status_code == 401


def test_feature_disabled_keeps_existing_api_compatible(api, monkeypatch):
    client, _ = api
    settings = get_settings()
    monkeypatch.setattr(settings, "solvo_demo_access_enabled", True)
    monkeypatch.setattr(settings, "solvo_demo_access_key", SecretStr(DEMO_KEY))
    monkeypatch.setattr(settings, "solvo_demo_session_enabled", False)
    response = client.get("/api/categories", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY})
    assert response.status_code == 200
    assert client.post(
        "/api/demo-session/acquire", headers={"X-SOLVO-DEMO-KEY": DEMO_KEY}
    ).json() == {"enabled": False, "session_token": None, "expires_at": None, "telegram_linked": False}


def test_public_routes_remain_session_independent_and_cors_allows_header(api, enabled):
    client, _ = api
    assert client.get("/api/public/assignments/invalid-token").status_code == 404
    webhook = client.post(
        "/api/telegram/webhook", json={},
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
    )
    assert webhook.status_code == 200
    preflight = client.options(
        "/api/categories",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-SOLVO-DEMO-KEY,X-SOLVO-DEMO-SESSION",
        },
    )
    assert preflight.status_code == 200
    allowed = preflight.headers["access-control-allow-headers"].lower()
    assert "x-solvo-demo-key" in allowed
    assert "x-solvo-demo-session" in allowed


def test_websocket_requires_demo_key_then_active_session_token(api, enabled):
    client, _ = api
    token = acquire(client)["session_token"]
    with client.websocket_connect("/ws/work-orders") as socket:
        socket.send_text(DEMO_KEY)
        assert socket.receive_text() == "demo-key-authorized"
        socket.send_text(token)
        assert socket.receive_text() == "authorized"

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/work-orders") as socket:
            socket.send_text(DEMO_KEY)
            assert socket.receive_text() == "demo-key-authorized"
            socket.send_text("wrong-session-token")
            socket.receive_text()
    assert closed.value.code == 1008
