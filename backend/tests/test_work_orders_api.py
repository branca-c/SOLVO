import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Reminder, WorkOrder, WorkOrderHistory, WorkOrderStatus
from app.services import work_orders

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
    for next_status in ("IN_CORSO", "EVASO", "CHIUSO"):
        assert client.patch(
            f"{URL}/{second['id']}/status", json={"status": next_status}
        ).status_code == 200
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


STATUS_PATHS = {
    "APERTO": [],
    "IN_CORSO": ["IN_CORSO"],
    "EVASO": ["IN_CORSO", "EVASO"],
    "CHIUSO": ["IN_CORSO", "EVASO", "CHIUSO"],
    "ANNULLATO": ["ANNULLATO"],
}
VALID_EDGES = {
    ("APERTO", "IN_CORSO"), ("APERTO", "ANNULLATO"),
    ("IN_CORSO", "EVASO"), ("IN_CORSO", "ANNULLATO"),
    ("EVASO", "CHIUSO"), ("EVASO", "IN_CORSO"),
}


@pytest.mark.parametrize("old", list(STATUS_PATHS))
@pytest.mark.parametrize("new", list(STATUS_PATHS))
def test_status_transition_policy_and_history(api, old, new):
    client, _ = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    for next_status in STATUS_PATHS[old]:
        assert client.patch(f"{url}/status", json={"status": next_status}).status_code == 200
    before = client.get(url).json()
    history_before = client.get(f"{url}/history").json()
    response = client.patch(f"{url}/status", json={"status": new})
    history_after = client.get(f"{url}/history").json()
    if old == new:
        assert response.status_code == 200
        assert response.json() == before
        assert history_after == history_before
    elif (old, new) in VALID_EDGES:
        assert response.status_code == 200
        assert response.json()["status"] == new
        assert client.get(url).json()["status"] == new
        assert len(history_after) == len(history_before) + 1
        assert history_after[0]["event_type"] == "STATUS_CHANGED"
        assert history_after[0]["description"] == f"Stato ODL: {old} → {new}"
        assert client.patch(f"{url}/status", json={"status": new}).status_code == 200
        assert client.get(f"{url}/history").json() == history_after
    else:
        assert response.status_code == 409
        assert old in response.json()["detail"] and new in response.json()["detail"]
        assert client.get(url).json() == before
        assert history_after == history_before


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


@pytest.mark.parametrize("method,suffix,body", [
    ("post", "reminders", {"created_by": 1}),
    ("get", "reminders", None), ("get", "history", None),
])
def test_missing_work_order_reminders_and_history(api, method, suffix, body):
    client, _ = api
    response = client.request(method, f"{URL}/999/{suffix}", json=body)
    assert response.status_code == 404


def test_create_multiple_reminders_and_history(api):
    client, engine = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    assert client.get(f"{url}/reminders").json() == []
    history = client.get(f"{url}/history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["event_type"] == "CREATED"
    for count in range(1, 4):
        response = client.post(f"{url}/reminders", json={"created_by": 1})
        assert response.status_code == 201
        reminder = response.json()
        assert reminder["work_order_id"] == original["id"]
        assert reminder["created_by"] == 1
        assert datetime.fromisoformat(reminder["created_at"])
        assert client.get(url).json()["reminders_count"] == count
        history = client.get(f"{url}/history").json()
        assert len(history) == count + 1
        assert history[0]["event_type"] == "REMINDER_CREATED"
        assert str(reminder["id"]) in history[0]["description"]
    with Session(engine) as db:
        assert len(db.scalars(select(Reminder)).all()) == 3
    assert client.patch(url, json={}).status_code == 200
    assert client.patch(url, json={"description": original["description"]}).status_code == 200
    assert client.get(f"{url}/history").json() == history


@pytest.mark.parametrize("body", [
    {}, {"created_by": None}, {"created_by": 999},
    {"created_by": 1, "created_at": "2020-01-01T00:00:00Z"},
    {"created_by": 1, "work_order_id": 999},
])
def test_invalid_reminder_creator_and_server_fields(api, body):
    client, _ = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    history = client.get(f"{url}/history").json()
    assert client.post(f"{url}/reminders", json=body).status_code == 422
    assert client.get(url).json() == original
    assert client.get(f"{url}/reminders").json() == []
    assert client.get(f"{url}/history").json() == history


def test_reminders_and_history_ordering_and_work_order_scope(api):
    client, engine = api
    first, second = create(client), create(client)
    url = f"{URL}/{first['id']}"
    for work_order in (first, second, first, first):
        assert client.post(
            f"{URL}/{work_order['id']}/reminders", json={"created_by": 1}
        ).status_code == 201
    with Session(engine) as db:
        reminders = db.scalars(select(Reminder).where(
            Reminder.work_order_id == first["id"]
        ).order_by(Reminder.id)).all()
        reminders[0].created_at = datetime(2022, 1, 1)
        reminders[1].created_at = reminders[2].created_at = datetime(2021, 1, 1)
        reminder_ids = [reminders[0].id, reminders[2].id, reminders[1].id]
        history = db.scalars(select(WorkOrderHistory).where(
            WorkOrderHistory.work_order_id == first["id"]
        ).order_by(WorkOrderHistory.id)).all()
        history[0].created_at = datetime(2020, 1, 1)
        history[1].created_at = datetime(2022, 1, 1)
        history[2].created_at = history[3].created_at = datetime(2021, 1, 1)
        history_ids = [history[1].id, history[3].id, history[2].id, history[0].id]
        db.commit()
    for suffix, ids in (("reminders", reminder_ids), ("history", history_ids)):
        response = client.get(f"{url}/{suffix}")
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == ids
        assert all(row["work_order_id"] == first["id"] for row in response.json())


@pytest.mark.parametrize("operation", ["reminder", "status"])
def test_history_failure_rolls_back_entire_mutation(api, operation):
    client, engine = api
    original = create(client)

    def fail_history_insert(mapper, connection, target):
        raise SQLAlchemyError("Simulated history storage failure")

    event.listen(WorkOrderHistory, "before_insert", fail_history_insert)
    try:
        with Session(engine) as db:
            work_order = db.get(WorkOrder, original["id"])
            with pytest.raises(SQLAlchemyError, match="Simulated history"):
                if operation == "reminder":
                    work_orders.create_reminder(db, work_order, 1)
                else:
                    work_orders.change_status(db, work_order, WorkOrderStatus.IN_CORSO)
            assert db.is_active
            db.refresh(work_order)
            assert work_order.reminders_count == 0
            assert work_order.status == WorkOrderStatus.APERTO
            assert db.scalars(select(Reminder)).all() == []
            assert len(db.scalars(select(WorkOrderHistory)).all()) == 1
    finally:
        event.remove(WorkOrderHistory, "before_insert", fail_history_insert)
    assert client.get(f"{URL}/{original['id']}").json() == original


def test_reminder_increment_uses_database_counter_not_stale_object(api):
    client, engine = api
    original = create(client)
    with Session(engine, expire_on_commit=False) as stale_db:
        stale_order = stale_db.get(WorkOrder, original["id"])
        stale_db.commit()
        assert client.post(
            f"{URL}/{original['id']}/reminders", json={"created_by": 1}
        ).status_code == 201
        assert stale_order.reminders_count == 0
        work_orders.create_reminder(stale_db, stale_order, 1)
    assert client.get(f"{URL}/{original['id']}").json()["reminders_count"] == 2


def test_status_policy_reloads_stale_status(api):
    client, engine = api
    original = create(client)
    url = f"{URL}/{original['id']}"
    with Session(engine, expire_on_commit=False) as stale_db:
        stale_order = stale_db.get(WorkOrder, original['id'])
        stale_db.commit()
        assert client.patch(f"{url}/status", json={"status": "ANNULLATO"}).status_code == 200
        assert stale_order.status == WorkOrderStatus.APERTO
        with pytest.raises(work_orders.InvalidTransitionError):
            work_orders.change_status(stale_db, stale_order, WorkOrderStatus.IN_CORSO)
    assert client.get(url).json()["status"] == "ANNULLATO"
    assert len(client.get(f"{url}/history").json()) == 2
