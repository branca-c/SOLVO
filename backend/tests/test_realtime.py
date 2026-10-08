import asyncio
from datetime import datetime

import pytest
from fastapi import WebSocketDisconnect
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import WorkOrder, WorkOrderHistory
from app.api import realtime as realtime_api
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


def test_delayed_old_generation_event_is_not_sent_to_current_session():
    class Socket:
        def __init__(self):
            self.messages = []
            self.close_codes = []
        async def accept(self): pass
        async def send_json(self, data): self.messages.append(data)
        async def close(self, code): self.close_codes.append(code)

    async def run():
        manager = realtime.ConnectionManager()
        manager.set_generation_resolver(lambda: (True, 2))
        old, current = Socket(), Socket()
        await manager.connect(old, generation=1)
        await manager.connect(current, generation=2)

        await manager.broadcast({'type': 'work_order.updated'}, generation=1)
        assert old.close_codes == [1008]
        assert old not in manager.clients
        assert current in manager.clients
        assert current.messages == []

        await manager.broadcast({'type': 'work_order.created'}, generation=2)
        assert current.messages == [{'type': 'work_order.created'}]

    asyncio.run(run())


def test_demo_access_websocket_disconnect_during_authentication_is_not_closed_again(monkeypatch):
    class Socket:
        def __init__(self):
            self.close_codes = []
        async def accept(self): pass
        async def receive_text(self): raise realtime_api.WebSocketDisconnect()
        async def close(self, code): self.close_codes.append(code)

    settings = get_settings()
    monkeypatch.setattr(settings, 'solvo_demo_access_enabled', True)
    socket = Socket()

    asyncio.run(realtime_api.work_order_events(socket, settings))

    assert socket.close_codes == []


def test_stale_generation_socket_is_closed_before_next_session_event(api, monkeypatch):
    client, _ = api
    settings = get_settings()
    monkeypatch.setattr(settings, 'solvo_demo_access_enabled', True)
    monkeypatch.setattr(settings, 'solvo_demo_access_key', SecretStr('ws-generation-key'))
    monkeypatch.setattr(settings, 'solvo_demo_session_enabled', True)
    first = client.post(
        '/api/demo-session/acquire', headers={'X-SOLVO-DEMO-KEY': 'ws-generation-key'}
    ).json()
    first_headers = {
        'X-SOLVO-DEMO-KEY': 'ws-generation-key',
        'X-SOLVO-DEMO-SESSION': first['session_token'],
    }

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect('/ws/work-orders') as socket:
            socket.send_text('ws-generation-key')
            assert socket.receive_text() == 'demo-key-authorized'
            socket.send_text(first['session_token'])
            assert socket.receive_text() == 'authorized'

            assert client.delete('/api/demo-session', headers=first_headers).status_code == 204
            second = client.post(
                '/api/demo-session/acquire',
                headers={'X-SOLVO-DEMO-KEY': 'ws-generation-key'},
            ).json()
            second_headers = {
                'X-SOLVO-DEMO-KEY': 'ws-generation-key',
                'X-SOLVO-DEMO-SESSION': second['session_token'],
            }
            response = client.post('/api/work-orders', headers=second_headers, json={
                'user_first_name': 'Demo', 'user_last_name': 'Due', 'user_phone': '1',
                'fault_address': 'Via Test', 'category_id': 1, 'priority': 'MEDIA',
                'description': 'Evento riservato alla nuova generation',
            })
            assert response.status_code == 201
            socket.receive_json()

    assert closed.value.code == 1008
    assert not realtime.manager.clients


@pytest.fixture
def published(monkeypatch):
    events = []
    monkeypatch.setattr(
        realtime.manager, 'submit',
        lambda event, generation=None: events.append(event),
    )
    return events


def test_work_order_events_noops_and_reminder(api, published):
    client, _ = api
    order = create(client)
    path = f"/api/work-orders/{order['id']}"
    assert client.patch(path, json={'description': 'Aggiornato'}).status_code == 200
    assert client.patch(path, json={'description': 'Aggiornato'}).status_code == 200
    assert client.patch(path + '/status', json={'status': 'APERTO'}).status_code == 200
    assert client.patch(path + '/status', json={'status': 'IN_CORSO'}).status_code == 200
    assert client.post(path + '/reminders', json={'created_by': 1, 'text': 'Richiesta aggiornamenti'}).status_code == 201
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
    def fail(data, generation=None):
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
