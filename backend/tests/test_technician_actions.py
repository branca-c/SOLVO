import pytest
import httpx
from pydantic import SecretStr

from app.core.config import get_settings
from app.services.assignment_links import sign_assignment, validate_token, InvalidActionTokenError
from app.services.notifications import MockNotificationProvider, TelegramNotificationProvider, NotificationUnavailableError
from tests.test_assignments_api import configure, start, history, assignment_url
from tests.test_work_orders_api import create


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'assignment_action_secret', SecretStr('test-only-secret-' * 4))
    monkeypatch.setattr(settings, 'notification_provider', 'mock')
    monkeypatch.setattr(settings, 'technician_action_base_url', 'http://127.0.0.1:5173')
    monkeypatch.setattr(settings, 'technician_action_token_ttl_minutes', 1440)
    return settings


@pytest.fixture
def pending(api):
    client, engine = api
    configure(engine)
    order = create(client)
    assignment = start(client, order)
    token = sign_assignment(assignment['id'], get_settings())
    return client, order, assignment, f'/api/public/assignments/{token}'


def test_signed_token_scope_expiration_and_tampering(configuration):
    token = sign_assignment(12, configuration, now=100)
    assert validate_token(token, configuration, now=101) == 12
    for invalid in [token.replace('v1.12.', 'v1.13.'), token + 'x', token[:-1], '12', 'bad.token', 'v2' + token[2:]]:
        with pytest.raises(InvalidActionTokenError):
            validate_token(invalid, configuration, now=101)
    with pytest.raises(InvalidActionTokenError):
        validate_token(token, configuration, now=86500)


def test_public_details_are_limited(pending):
    client, order, assignment, path = pending
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {
        'id': assignment['id'], 'status': 'PENDING', 'technician_name': 'Tecnico 10 Rossi',
        'work_order_code': order['code'], 'requester_name': f"{order['user_first_name']} {order['user_last_name']}",
        'requester_phone': order['user_phone'], 'fault_address': order['fault_address'],
        'category': 'Elettrico', 'priority': order['priority'], 'description': order['description'],
        'work_order_status': 'APERTO', 'rejection_notes': None,
    }


def test_public_accept_and_duplicate(pending):
    client, order, _, path = pending
    result = client.post(path + '/accept')
    assert result.status_code == 200
    assert result.json()['status'] == 'ACCEPTED'
    assert result.json()['work_order_status'] == 'IN_CORSO'
    before = history(client, order)
    assert client.post(path + '/accept').status_code == 409
    assert client.post(path + '/reject').status_code == 409
    assert history(client, order) == before


@pytest.mark.parametrize('body', [{}, {'rejection_notes': 'Non disponibile'}])
def test_public_reject_routes_and_only_returns_own_assignment(pending, body):
    client, order, assignment, path = pending
    response = client.post(path + '/reject', json=body)
    assert response.status_code == 200
    assert response.json()['id'] == assignment['id']
    assert response.json()['status'] == 'REJECTED'
    assert response.json()['rejection_notes'] == body.get('rejection_notes')
    following = client.get(assignment_url(order) + '/current').json()
    assert following['status'] == 'PENDING'
    assert following['id'] != assignment['id']
    assert following['attempt_number'] == 2
    assert client.post(path + '/accept').status_code == 409


def test_reject_exhaustion_preserves_pending(api):
    client, engine = api
    configure(engine, ((1, False),))
    order = create(client)
    assignment = start(client, order)
    path = '/api/public/assignments/' + sign_assignment(assignment['id'], get_settings())
    before = history(client, order)
    assert client.post(path + '/reject', json={}).status_code == 409
    assert client.get(path).json()['status'] == 'PENDING'
    assert history(client, order) == before


@pytest.mark.parametrize('suffix,method', [('', 'get'), ('/accept', 'post'), ('/reject', 'post')])
def test_invalid_expired_missing_tokens(api, configuration, suffix, method):
    client, _ = api
    for token in ['tampered', sign_assignment(999, configuration), sign_assignment(1, configuration, now=0)]:
        assert client.request(method, '/api/public/assignments/' + token + suffix).status_code == 404


def test_notify_mock_message_and_history(pending, monkeypatch):
    client, order, assignment, _ = pending
    def network_forbidden(*args, **kwargs):
        raise AssertionError('Mock must not construct an HTTP client')
    monkeypatch.setattr(httpx, 'Client', network_forbidden)
    captured = []
    original = MockNotificationProvider.send
    def capture(self, phone, message):
        captured.append((phone, message))
        return original(self, phone, message)
    monkeypatch.setattr(MockNotificationProvider, 'send', capture)
    response = client.post(f"/api/assignments/{assignment['id']}/notify")
    assert response.status_code == 200
    result = response.json()
    assert result['provider'] == 'mock'
    assert result['status'] == 'simulated'
    assert result['action_url'].startswith('http://127.0.0.1:5173/tecnico/assegnazione/v1.')
    message = captured[0][1]
    for expected in ['SOLVO', order['code'], order['priority'], order['fault_address'], 'Elettrico', result['action_url']]:
        assert expected in message
    assert captured[0][0] == assignment['technician_id']
    assert order['user_phone'] not in message
    events = history(client, order)
    assert events[0]['event_type'] == 'ASSIGNMENT_NOTIFICATION_SENT'
    assert result['action_url'] not in events[0]['description']
    assert client.get('/api/public/assignments/' + result['action_url'].rsplit('/', 1)[1]).status_code == 200


def test_notify_conflicts_and_missing(pending):
    client, _, assignment, path = pending
    assert client.post('/api/assignments/999/notify').status_code == 404
    assert client.post(path + '/accept').status_code == 200
    assert client.post(f"/api/assignments/{assignment['id']}/notify").status_code == 409


@pytest.mark.parametrize('action', ['accept', 'reject', 'notify'])
def test_terminal_order_blocks_public_and_notify(pending, action):
    client, order, assignment, path = pending
    client.patch(f"/api/work-orders/{order['id']}/status", json={'status': 'ANNULLATO'})
    target = f"/api/assignments/{assignment['id']}/notify" if action == 'notify' else path + '/' + action
    assert client.post(target).status_code == 409


def test_missing_secret_fails_closed(pending, monkeypatch):
    client, _, assignment, path = pending
    monkeypatch.setattr(get_settings(), 'assignment_action_secret', SecretStr(''))
    assert client.get(path).status_code == 503
    assert client.post(f"/api/assignments/{assignment['id']}/notify").status_code == 503


def test_notify_provider_failure_has_no_success_history(pending, monkeypatch):
    client, order, assignment, _ = pending
    before = history(client, order)
    def fail(*args):
        raise NotificationUnavailableError('Invio non disponibile')
    monkeypatch.setattr(MockNotificationProvider, 'send', fail)
    assert client.post(f"/api/assignments/{assignment['id']}/notify").status_code == 503
    assert history(client, order) == before
    assert client.get(assignment_url(order) + '/current').json()['status'] == 'PENDING'


def test_telegram_notify_request_and_server_only_token(pending, monkeypatch, caplog):
    import json
    import logging
    client, order, assignment, _ = pending
    settings = get_settings()
    monkeypatch.setattr(settings, 'notification_provider', 'telegram')
    monkeypatch.setattr(settings, 'telegram_bot_token', SecretStr('123456:test-private-token'))
    monkeypatch.setattr(settings, 'telegram_demo_chat_id', '987654')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'ok': True, 'result': {'message_id': 42}})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with caplog.at_level(logging.DEBUG):
        response = client.post(f"/api/assignments/{assignment['id']}/notify")
    assert response.status_code == 200
    result = response.json()
    assert result['provider'] == 'telegram'
    assert result['message_id'] == '42'
    assert result['status'] == 'submitted'
    assert len(requests) == 1
    assert requests[0].method == 'POST'
    assert str(requests[0].url) == 'https://api.telegram.org/bot123456:test-private-token/sendMessage'
    payload = json.loads(requests[0].content)
    assert payload['chat_id'] == '987654'
    assert payload['link_preview_options'] == {'is_disabled': True}
    assert 'reply_markup' not in payload
    assert 'parse_mode' not in payload
    for expected in ['SOLVO', order['code'], order['priority'], order['fault_address'], 'Elettrico', result['action_url']]:
        assert expected in payload['text']
    for private in [order['user_phone'], order['user_first_name'], order['user_last_name']]:
        assert private not in payload['text']
    events = history(client, order)
    assert events[0]['event_type'] == 'ASSIGNMENT_NOTIFICATION_SENT'
    assert 'telegram' in events[0]['description']
    assert 'test-private-token' not in response.text + str(events) + caplog.text
    assert result['action_url'] not in events[0]['description']
    token = result['action_url'].rsplit('/', 1)[1]
    assert validate_token(token, settings) == assignment['id']


@pytest.mark.parametrize('status,body', [
    (401, {'description': 'private'}), (429, {'ok': False}),
    (200, {'ok': False}), (200, []), (200, {'ok': True, 'result': None}),
    (200, {'ok': True, 'result': {'message_id': True}}),
    (200, {'ok': True, 'result': {'message_id': 'private'}}),
])
def test_telegram_error_sanitized(monkeypatch, status, body):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)), **kwargs))
    with pytest.raises(NotificationUnavailableError) as error:
        TelegramNotificationProvider('123:private', '987').send(1, 'text')
    assert 'private' not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize('provider,token,chat', [
    ('telegram', '', '987'), ('telegram', '123:token', ''),
    ('telegram', 'invalid/token', '987'), ('telegram', '123:token', 'invalid'),
    ('unknown', '', ''),
])
def test_invalid_provider_configuration_does_not_mutate(pending, monkeypatch, provider, token, chat):
    client, order, assignment, _ = pending
    settings = get_settings()
    monkeypatch.setattr(settings, 'notification_provider', provider)
    monkeypatch.setattr(settings, 'telegram_bot_token', SecretStr(token))
    monkeypatch.setattr(settings, 'telegram_demo_chat_id', chat)
    before = history(client, order)
    response = client.post(f"/api/assignments/{assignment['id']}/notify")
    assert response.status_code == 503
    if provider == 'telegram':
        assert 'TELEGRAM_BOT_TOKEN e TELEGRAM_DEMO_CHAT_ID' in response.json()['detail']
    assert history(client, order) == before


def test_mock_is_deterministic():
    provider = MockNotificationProvider()
    assert provider.send(1, 'message') == provider.send(1, 'message')
    assert provider.send(1, 'message') != provider.send(2, 'message')


def test_telegram_timeout_is_not_retried(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('private', request=request)
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(NotificationUnavailableError, match='Invio Telegram non confermato'):
        TelegramNotificationProvider('123:private', '987').send(1, 'text')
    assert len(calls) == 1


def test_secret_rotation_revokes_existing_token(pending, monkeypatch):
    client, _, _, path = pending
    monkeypatch.setattr(get_settings(), 'assignment_action_secret', SecretStr('a-different-secret-' * 3))
    assert client.get(path).status_code == 404
    assert client.post(path + '/accept').status_code == 404


def test_notify_commit_failure_rolls_back_history_and_preserves_assignment(api, configuration):
    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from app.models import WorkOrderHistory
    from app.services.assignment_notifications import notify

    client, engine = api
    configure(engine)
    order = create(client)
    assignment = start(client, order)
    before = history(client, order)
    def fail(*args):
        raise SQLAlchemyError('history storage unavailable')
    event.listen(WorkOrderHistory, 'before_insert', fail)
    try:
        with Session(engine) as db:
            with pytest.raises(SQLAlchemyError):
                notify(db, assignment['id'], configuration)
            assert db.is_active
    finally:
        event.remove(WorkOrderHistory, 'before_insert', fail)
    assert history(client, order) == before
    assert client.get(assignment_url(order) + '/current').json()['status'] == 'PENDING'
