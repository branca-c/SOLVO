import asyncio
from datetime import datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import WorkOrder, WorkOrderHistory
from app.core.config import get_settings
from app.services import realtime, work_orders
from app.schemas.work_order import WorkOrderStatusUpdate
from app.services.assignment_links import sign_assignment
from tests.test_work_orders_api import create
from tests.test_assignments_api import configure, start


def test_multiple_websocket_clients_and_disconnect(api):
    client, _ = api
    with client.websocket_connect('/ws/work-orders') as first:
        with client.websocket_connect('/ws/work-orders') as second:
            order = create(client)
            one, two = first.receive_json(), second.receive_json()
            assert one == two
            assert one['type'] == 'work_order.created'
            assert one['work_order_id'] == order['id']
            assert set(one) == {'type', 'work_order_id', 'timestamp'}
            assert datetime.fromisoformat(one['timestamp'])
        client.patch(f"/api/work-orders/{order['id']}/status", json={'status': 'IN_CORSO'})
        assert first.receive_json()['type'] == 'work_order.status_changed'
    assert not realtime.manager.clients


def test_broken_client_does_not_block_healthy_client():
    class Socket:
        def __init__(self, broken=False):
            self.broken = broken
            self.messages = []
        async def accept(self): pass
        async def send_json(self, data):
            if self.broken: raise RuntimeError('disconnected')
            self.messages.append(data)
        async def close(self, code): pass
    async def run():
        manager = realtime.ConnectionManager()
        bad, good = Socket(True), Socket()
        await manager.connect(bad)
        await manager.connect(good)
        await manager.broadcast({'type': 'work_order.updated'})
        assert bad not in manager.clients
        assert good.messages == [{'type': 'work_order.updated'}]
    asyncio.run(run())


@pytest.fixture
def published(monkeypatch):
    events = []
    monkeypatch.setattr(realtime.manager, 'submit', events.append)
    return events


def test_work_order_events_noops_and_reminder(api, published):
    client, _ = api
    order = create(client)
    path = f"/api/work-orders/{order['id']}"
    assert client.patch(path, json={'description': 'Aggiornato'}).status_code == 200
    assert client.patch(path, json={'description': 'Aggiornato'}).status_code == 200
    assert client.patch(path + '/status', json={'status': 'APERTO'}).status_code == 200
    assert client.patch(path + '/status', json={'status': 'IN_CORSO'}).status_code == 200
    assert client.post(path + '/reminders', json={'created_by': 1}).status_code == 201
    assert client.delete(path).status_code == 204
    assert [item['type'] for item in published] == ['work_order.created', 'work_order.updated', 'work_order.status_changed', 'reminder.created', 'work_order.deleted']
    assert all(item['work_order_id'] == order['id'] for item in published)


def test_assignment_and_public_action_events(api, published, monkeypatch):
    client, engine = api
    settings = get_settings()
    monkeypatch.setattr(settings, 'assignment_action_secret', SecretStr('test-secret-' * 4))
    monkeypatch.setattr(settings, 'notification_provider', 'mock')
    configure(engine)
    order = create(client)
    first = start(client, order)
    published.clear()
    token = sign_assignment(first['id'], settings)
    assert client.post(f'/api/public/assignments/{token}/reject').status_code == 200
    current = client.get(f"/api/work-orders/{order['id']}/assignments/current").json()
    assert client.post(f"/api/assignments/{current['id']}/no-response").status_code == 200
    assert client.post(f"/api/work-orders/{order['id']}/assignments/escalate-team-leader").status_code == 201
    current = client.get(f"/api/work-orders/{order['id']}/assignments/current").json()
    assert client.post(f"/api/assignments/{current['id']}/notify").status_code == 200
    token = sign_assignment(current['id'], settings)
    assert client.post(f'/api/public/assignments/{token}/accept').status_code == 200
    assert client.post(f'/api/public/assignments/{token}/accept').status_code == 409
    assert [item['type'] for item in published] == [
        'assignment.rejected', 'assignment.created', 'assignment.no_response', 'assignment.created',
        'assignment.escalated', 'assignment.created', 'assignment.notification_sent',
        'assignment.accepted', 'work_order.status_changed',
    ]


def test_publish_is_after_commit_and_failure_does_not_break_business_operation(api, monkeypatch):
    client, engine = api
    observed = []
    def fail(data):
        with Session(engine) as db:
            observed.append(db.get(WorkOrder, data['work_order_id']).code)
        raise RuntimeError('broken publisher')
    monkeypatch.setattr(realtime.manager, 'submit', fail)
    order = create(client)
    assert observed == [order['code']]
    assert client.get(f"/api/work-orders/{order['id']}").status_code == 200


def test_failed_commit_does_not_emit_event(api, published):
    client, engine = api
    order = create(client)
    published.clear()
    def fail(*args): raise SQLAlchemyError('storage unavailable')
    event.listen(WorkOrderHistory, 'before_insert', fail)
    try:
        with Session(engine) as db:
            with pytest.raises(SQLAlchemyError):
                work_orders.change_status(db, db.get(WorkOrder, order['id']), WorkOrderStatusUpdate(status='IN_CORSO').status)
    finally:
        event.remove(WorkOrderHistory, 'before_insert', fail)
    assert published == []
