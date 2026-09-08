import pytest
import httpx
from pydantic import SecretStr

from app.core.config import get_settings
from app.services.assignment_links import sign_assignment, validate_token, InvalidActionTokenError
from app.services.whatsapp import MockWhatsAppProvider, TwilioWhatsAppProvider, NotificationUnavailableError
from tests.test_assignments_api import configure, start, history, assignment_url
from tests.test_work_orders_api import create


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'assignment_action_secret', SecretStr('test-only-secret-' * 4))
    monkeypatch.setattr(settings, 'whatsapp_provider', 'mock')
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
        raise AssertionError('Mock must not contact Twilio')
    monkeypatch.setattr(httpx, 'Client', network_forbidden)
    captured = []
    original = MockWhatsAppProvider.send
    def capture(self, phone, message):
        captured.append((phone, message))
        return original(self, phone, message)
    monkeypatch.setattr(MockWhatsAppProvider, 'send', capture)
    response = client.post(f"/api/assignments/{assignment['id']}/notify")
    assert response.status_code == 200
    result = response.json()
    assert result['provider'] == 'mock'
    assert result['status'] == 'simulated'
    assert result['action_url'].startswith('http://127.0.0.1:5173/tecnico/assegnazione/v1.')
    message = captured[0][1]
    for expected in ['SOLVO', order['code'], order['priority'], order['fault_address'], 'Elettrico', result['action_url']]:
        assert expected in message
    assert captured[0][0] == assignment['technician']['phone']
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
    monkeypatch.setattr(MockWhatsAppProvider, 'send', fail)
    assert client.post(f"/api/assignments/{assignment['id']}/notify").status_code == 503
    assert history(client, order) == before
    assert client.get(assignment_url(order) + '/current').json()['status'] == 'PENDING'


def test_twilio_request_uses_sandbox_addresses_without_live_network(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={'sid': 'SM' + 'a' * 32, 'status': 'queued'})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    provider = TwilioWhatsAppProvider('AC' + 'b' * 32, 'test-token', 'whatsapp:+14155238886')
    result = provider.send('+393331234567', 'SOLVO link')
    assert result.status == 'submitted'
    assert str(requests[0].url) == 'https://api.twilio.com/2010-04-01/Accounts/AC' + 'b' * 32 + '/Messages.json'
    assert b'To=whatsapp%3A%2B393331234567' in requests[0].content
    assert b'From=whatsapp%3A%2B14155238886' in requests[0].content


def test_twilio_error_sanitized(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={'message': 'secret'})), **kwargs))
    with pytest.raises(NotificationUnavailableError) as error:
        TwilioWhatsAppProvider('AC' + 'b' * 32, 'private', '+14155238886').send('+393331234567', 'text')
    assert 'private' not in str(error.value)
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('provider', ['twilio', 'unknown'])
def test_invalid_provider_configuration_does_not_mutate(pending, monkeypatch, provider):
    client, order, assignment, _ = pending
    settings = get_settings()
    monkeypatch.setattr(settings, 'whatsapp_provider', provider)
    monkeypatch.setattr(settings, 'twilio_account_sid', '')
    before = history(client, order)
    assert client.post(f"/api/assignments/{assignment['id']}/notify").status_code == 503
    assert history(client, order) == before


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
