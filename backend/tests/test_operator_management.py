import pytest
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
from app.models import WorkOrderNote, WorkOrderHistory, Technician
from app.scripts.seed_demo import seed_demo


def create_order(client):
    return client.post('/api/work-orders', json=dict(user_first_name='Ada', user_last_name='Rossi',
        user_phone='123', fault_address='Via Roma 1', category_id=1, priority='MEDIA', description='Guasto')).json()


def test_notes_create_order_history_and_delete(api, monkeypatch):
    client, engine = api
    published = []
    monkeypatch.setattr('app.services.work_orders.publish', lambda *args: published.append(args))
    order = create_order(client)
    path = f"/api/work-orders/{order['id']}"
    first = client.post(path + '/notes', json={'text': '  Prima nota  '})
    assert first.status_code == 201
    assert first.json()['text'] == 'Prima nota'
    assert first.json()['created_by'] is None
    assert first.json()['created_at']
    second = client.post(path + '/notes', json={'text': 'Seconda nota'}).json()
    assert [n['id'] for n in client.get(path + '/notes').json()] == [second['id'], first.json()['id']]
    assert client.get(path).json()['description'] == 'Guasto'
    history = client.get(path + '/history').json()
    assert len([h for h in history if h['event_type'] == 'NOTE_ADDED']) == 2
    assert published[-1] == ('work_order.updated', order['id'])
    assert client.delete(path).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrderNote)) == 0
        assert db.scalar(select(func.count()).select_from(WorkOrderHistory)) == 0


@pytest.mark.parametrize('text', ['', '   ', '\n\t'])
def test_empty_notes_rejected(api, text):
    client, _ = api
    order = create_order(client)
    assert client.post(f"/api/work-orders/{order['id']}/notes", json={'text': text}).status_code == 422


def test_notes_missing_order(api):
    client, _ = api
    assert client.get('/api/work-orders/999/notes').status_code == 404
    assert client.post('/api/work-orders/999/notes', json={'text': 'Nota'}).status_code == 404


def test_note_history_failure_rolls_back(api, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    client, engine = api
    order = create_order(client)
    published = []
    monkeypatch.setattr('app.services.work_orders.publish', lambda *args: published.append(args))
    def fail(mapper, connection, target):
        if target.event_type == 'NOTE_ADDED':
            raise SQLAlchemyError('history failure')
    event.listen(WorkOrderHistory, 'before_insert', fail)
    try:
        with pytest.raises(SQLAlchemyError):
            client.post(f"/api/work-orders/{order['id']}/notes", json={'text': 'Nota'})
    finally:
        event.remove(WorkOrderHistory, 'before_insert', fail)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(WorkOrderNote)) == 0
    assert published == []


def test_technician_contact_update_keeps_routing(api):
    client, engine = api
    with Session(engine) as db:
        seed_demo(db)
    tech = client.get('/api/technicians?category_id=1').json()[0]
    path = f"/api/technicians/{tech['id']}"
    response = client.patch(path, json={'first_name': 'Mario', 'last_name': 'Verdi'})
    assert response.status_code == 200
    assert response.json()['first_name'] == 'Mario'
    assert response.json()['last_name'] == 'Verdi'
    response = client.patch(path, json={'phone': '+39 123', 'email': 'mario@example.com'})
    assert response.json()['phone'] == '+39 123'
    assert response.json()['email'] == 'mario@example.com'
    for field in ['id', 'category_id', 'escalation_order', 'is_team_leader']:
        assert client.patch(path, json={field: 2}).status_code == 422
    for field in ['first_name', 'last_name', 'phone']:
        for value in [' ', '', None]:
            assert client.patch(path, json={field: value}).status_code == 422
    assert client.patch('/api/technicians/99999', json={'phone': '123'}).status_code == 404
    order = create_order(client)
    assignment = client.post(f"/api/work-orders/{order['id']}/assignments/start").json()
    assert assignment['technician_id'] == tech['id']
    assert assignment['technician']['first_name'] == 'Mario'
    assert assignment['technician']['phone'] == '+39 123'
    assert client.patch(path, json={'email': None}).json()['email'] is None
