import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.test_work_orders_api import create


def test_reminder_text_is_trimmed_returned_and_not_duplicated_in_history(api):
    client, _ = api
    order = create(client)
    path = f"/api/work-orders/{order['id']}"
    content = 'Richiesta aggiornamenti ' + 'x' * 1900
    response = client.post(path + '/reminders', json={'created_by': 1, 'text': f'  {content}  '})
    assert response.status_code == 201
    reminder = response.json()
    assert reminder['text'] == content
    assert client.get(path + '/reminders').json() == [reminder]
    assert client.get(path).json()['reminders_count'] == 1
    history = client.get(path + '/history').json()[0]
    assert history['event_type'] == 'REMINDER_CREATED'
    assert str(reminder['id']) in history['description']
    assert content not in history['description']
    assert len(history['description']) < 200


@pytest.mark.parametrize('body', [
    {'created_by': 1}, {'created_by': 1, 'text': ''},
    {'created_by': 1, 'text': ' \n\t '}, {'created_by': 1, 'text': None},
    {'created_by': 1, 'text': 'x' * 2001},
])
def test_invalid_reminder_text_has_no_side_effects(api, body):
    client, _ = api
    order = create(client)
    path = f"/api/work-orders/{order['id']}"
    before = client.get(path + '/history').json()
    assert client.post(path + '/reminders', json=body).status_code == 422
    assert client.get(path).json()['reminders_count'] == 0
    assert client.get(path + '/reminders').json() == []
    assert client.get(path + '/history').json() == before


def test_reminder_text_maximum_length(api):
    client, _ = api
    order = create(client)
    assert client.post(f"/api/work-orders/{order['id']}/reminders",
                       json={'created_by': 1, 'text': 'x' * 2000}).status_code == 201


@pytest.mark.parametrize('legacy_count', [0, 2])
def test_reminder_migration_upgrade_and_downgrade_preserve_legacy_data(legacy_count):
    path = Path(__file__).parents[1] / 'migrations/versions/20260916_0003_reminder_text.py'
    spec = importlib.util.spec_from_file_location('reminder_text_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE reminders (id INTEGER PRIMARY KEY, work_order_id INTEGER NOT NULL, created_by INTEGER NOT NULL, created_at DATETIME NOT NULL)'))
        for i in range(legacy_count):
            connection.execute(text("INSERT INTO reminders VALUES (:id, 7, 1, '2026-09-01 12:00:00')"), {'id': i + 1})
        original = connection.execute(text('SELECT * FROM reminders ORDER BY id')).all()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.execute(text('SELECT id, work_order_id, created_by, created_at FROM reminders ORDER BY id')).all() == original
        assert connection.execute(text('SELECT text FROM reminders')).scalars().all() == [migration.LEGACY_TEXT] * legacy_count
        column = next(c for c in inspect(connection).get_columns('reminders') if c['name'] == 'text')
        assert column['nullable'] is False
        assert column['default'] is None
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO reminders (id, work_order_id, created_by, created_at) VALUES (99, 7, 1, '2026-09-01')"))
        migration.downgrade()
        assert 'text' not in {c['name'] for c in inspect(connection).get_columns('reminders')}
        assert connection.execute(text('SELECT * FROM reminders ORDER BY id')).all() == original
    engine.dispose()
