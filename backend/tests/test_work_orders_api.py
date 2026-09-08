import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Category, WorkOrder, WorkOrderHistory

URL = "/api/work-orders"
PAYLOAD = {
    "user_first_name": "Ada",
    "user_last_name": "Rossi",
    "user_phone": "+390000000001",
    "fault_address": "Via Roma 1",
    "category_id": 1,
    "priority": "MEDIA",
    "description": "Presa non funzionante",
}


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Category(id=1, name="Elettrico"), Category(id=2, name="Idraulico")])
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def create(client, **changes):
    response = client.post(URL, json={**PAYLOAD, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_defaults_code_and_history(api):
    client, engine = api
    first = create(client)
    second = create(client, user_email="ada@example.com")
    assert first["id"] != second["id"]
    assert first["code"] != second["code"]
    assert re.fullmatch(r"SOLVO-\d{8}-[0-9A-F]{16}", first["code"])
    assert first["code"].split("-")[1] == datetime.now(timezone.utc).strftime("%Y%m%d")
    assert first["status"] == "APERTO"
    assert first["reminders_count"] == 0
    assert first["user_email"] is None
    assert second["user_email"] == "ada@example.com"
    assert datetime.fromisoformat(first["created_at"])
    assert datetime.fromisoformat(first["updated_at"])
    for key, value in PAYLOAD.items():
        assert first[key] == value
    with Session(engine) as db:
        history = db.scalars(select(WorkOrderHistory)).all()
        assert [entry.event_type for entry in history] == ["CREATED", "CREATED"]


def test_list_newest_first_and_filters(api):
    client, engine = api
    assert client.get(URL).json() == []
    first = create(client)
    second = create(client, category_id=2, priority="URGENTE")
    third = create(client)
    # Explicit times also verify ordering takes precedence over the ID tie-breaker.
    with Session(engine) as db:
        db.get(WorkOrder, first["id"]).created_at = datetime(2020, 1, 1)
        db.get(WorkOrder, second["id"]).created_at = datetime(2022, 1, 1)
        db.get(WorkOrder, third["id"]).created_at = datetime(2021, 1, 1)
        db.commit()
    client.patch(f"{URL}/{second['id']}/status", json={"status": "CHIUSO"})
    response = client.get(URL)
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [second["id"], third["id"], first["id"]]
    for params in (
        {"status": "CHIUSO"}, {"priority": "URGENTE"}, {"category_id": 2},
        {"status": "CHIUSO", "priority": "URGENTE", "category_id": 2},
    ):
        response = client.get(URL, params=params)
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [second["id"]]
    assert client.get(URL, params={"status": "APERTO", "category_id": 2}).json() == []


def test_get_and_patch(api):
    client, _ = api
    original = create(client, user_email="ada@example.com")
    url = f"{URL}/{original['id']}"
    assert client.get(url).json() == original
    changes = {
        "user_first_name": "Luca", "user_last_name": "Bianchi", "user_phone": "12345",
        "user_email": None, "fault_address": "Via Milano 2", "category_id": 2,
        "priority": "ALTA", "description": "Perdita acqua",
    }
    response = client.patch(url, json=changes)
    assert response.status_code == 200
    for key, value in changes.items():
        assert response.json()[key] == value
    for key in ("id", "code", "created_at", "status", "reminders_count"):
        assert response.json()[key] == original[key]
    assert client.get(url).json() == response.json()
    partial = client.patch(url, json={"description": "Nuova descrizione"})
    assert partial.json()["user_last_name"] == "Bianchi"
    assert client.patch(url, json={}).json() == partial.json()


@pytest.mark.parametrize("status", ["APERTO", "IN_CORSO", "EVASO", "CHIUSO", "ANNULLATO"])
def test_change_status_and_repeated_request(api, status):
    client, engine = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    for _ in range(2):
        response = client.patch(f"{url}/status", json={"status": status})
        assert response.status_code == 200
        assert response.json()["status"] == status
    assert client.get(url).json()["status"] == status
    with Session(engine) as db:
        history = db.scalars(select(WorkOrderHistory).order_by(WorkOrderHistory.id)).all()
        assert len(history) == (1 if status == "APERTO" else 2)
        if status != "APERTO":
            assert history[-1].event_type == "STATUS_CHANGED"
            assert history[-1].description == f"Stato ODL: APERTO → {status}"
    # No workflow restrictions are imposed by this API slice.
    assert client.patch(f"{url}/status", json={"status": "APERTO"}).status_code == 200


def test_delete(api):
    client, engine = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    response = client.delete(url)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404
    assert client.get(URL).json() == []
    with Session(engine) as db:
        assert db.scalars(select(WorkOrderHistory)).all() == []


@pytest.mark.parametrize("method,suffix,body", [
    ("get", "", None), ("patch", "", {"description": "Guasto"}),
    ("patch", "/status", {"status": "EVASO"}), ("delete", "", None),
])
def test_missing_work_order(api, method, suffix, body):
    client, _ = api
    assert client.request(method, f"{URL}/999{suffix}", json=body).status_code == 404


def test_invalid_category_is_atomic(api):
    client, engine = api
    assert client.post(URL, json={**PAYLOAD, "category_id": 999}).status_code == 422
    assert client.get(URL).json() == []
    original = create(client)
    url = f"{URL}/{original['id']}"
    response = client.patch(url, json={"category_id": 999, "description": "Modificata"})
    assert response.status_code == 422
    assert client.get(url).json() == original
    with Session(engine) as db:
        assert len(db.scalars(select(WorkOrderHistory)).all()) == 1


@pytest.mark.parametrize("field,value", [
    ("id", 88), ("code", "CUSTOM"), ("created_at", "2020-01-01T00:00:00Z"),
    ("updated_at", "2020-01-01T00:00:00Z"), ("reminders_count", 4), ("status", "CHIUSO"),
])
def test_server_fields_are_rejected(api, field, value):
    client, _ = api
    assert client.post(URL, json={**PAYLOAD, field: value}).status_code == 422
    original = create(client)
    url = f"{URL}/{original['id']}"
    assert client.patch(url, json={field: value}).status_code == 422
    assert client.get(url).json() == original


@pytest.mark.parametrize("field", list(PAYLOAD))
def test_required_fields_reject_null(api, field):
    client, _ = api
    assert client.post(URL, json={**PAYLOAD, field: None}).status_code == 422
    original = create(client)
    assert client.patch(f"{URL}/{original['id']}", json={field: None}).status_code == 422


def test_invalid_enums(api):
    client, _ = api
    assert client.post(URL, json={**PAYLOAD, "priority": "CRITICA"}).status_code == 422
    original = create(client)
    url = f"{URL}/{original['id']}"
    assert client.patch(url, json={"priority": "CRITICA"}).status_code == 422
    for value in ("COMPLETATO", None):
        assert client.patch(f"{url}/status", json={"status": value}).status_code == 422
    for params in ({"status": "COMPLETATO"}, {"priority": "CRITICA"}):
        assert client.get(URL, params=params).status_code == 422
    assert client.get(url).json() == original
