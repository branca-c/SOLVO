from datetime import datetime

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Assignment, AssignmentStatus, Technician, WorkOrder, WorkOrderHistory
from app.services import assignments
from tests.test_work_orders_api import URL, create


def configure(engine, entries=((30, False), (10, False), (1, True), (20, False)), category_id=1):
    with Session(engine) as db:
        technicians = [Technician(
            first_name=f"Tecnico {order}", last_name="Rossi", phone=f"+39000{order}",
            category_id=category_id, escalation_order=order, is_team_leader=leader,
        ) for order, leader in entries]
        db.add_all(technicians)
        db.commit()
        return {item.escalation_order: item.id for item in technicians}


def assignment_url(work_order):
    return f"{URL}/{work_order['id']}/assignments"


def start(client, work_order):
    response = client.post(f"{assignment_url(work_order)}/start")
    assert response.status_code == 201, response.text
    return response.json()


def history(client, work_order):
    return client.get(f"{URL}/{work_order['id']}/history").json()


def test_start_uses_category_and_configured_order(api):
    client, engine = api
    configure(engine, ((1, False),), category_id=2)
    ids = configure(engine)
    work_order = create(client)
    assert client.get(assignment_url(work_order)).json() == []
    assert client.get(f"{assignment_url(work_order)}/current").status_code == 404
    assignment = start(client, work_order)
    assert assignment['technician_id'] == ids[10]
    assert assignment['technician']['id'] == ids[10]
    assert assignment['technician']['first_name'] == 'Tecnico 10'
    assert assignment['technician']['category_id'] == 1
    assert assignment['status'] == 'PENDING'
    assert assignment['attempt_number'] == 1
    assert assignment['work_order_id'] == work_order['id']
    assert datetime.fromisoformat(assignment['sent_at'])
    assert assignment['responded_at'] is None
    assert assignment['rejection_notes'] is None
    assert history(client, work_order)[0]['event_type'] == 'ASSIGNMENT_STARTED'
    assert client.get(f"{assignment_url(work_order)}/current").json() == assignment


def test_reject_and_no_response_route_all_normals_then_leader(api):
    client, engine = api
    ids = configure(engine)
    work_order = create(client)
    current = start(client, work_order)
    seen = [current['technician_id']]
    for attempt, (action, next_order) in enumerate(
        [('reject', 20), ('no-response', 30), ('reject', 1)], start=2
    ):
        kwargs = {'json': {'rejection_notes': 'Intervento non gestibile'}} if action == 'reject' else {}
        response = client.post(f"/api/assignments/{current['id']}/{action}", **kwargs)
        assert response.status_code == 200
        previous = response.json()
        assert previous['status'] == ('REJECTED' if action == 'reject' else 'NO_RESPONSE')
        if action == 'reject':
            assert previous['rejection_notes'] == 'Intervento non gestibile'
            assert datetime.fromisoformat(previous['responded_at'])
        else:
            assert previous['responded_at'] is None
            assert previous['rejection_notes'] is None
        current = client.get(f"{assignment_url(work_order)}/current").json()
        assert current['status'] == 'PENDING'
        assert current['attempt_number'] == attempt
        assert current['technician_id'] == ids[next_order]
        seen.append(current['technician_id'])
        events = history(client, work_order)
        assert events[0]['event_type'] == 'ASSIGNMENT_STARTED'
        assert events[1]['event_type'] == f"ASSIGNMENT_{previous['status']}"
    assert len(set(seen)) == 4
    listed = client.get(assignment_url(work_order))
    assert listed.status_code == 200
    assert [item['attempt_number'] for item in listed.json()] == [1, 2, 3, 4]
    assert [item['technician_id'] for item in listed.json()] == seen
    assert listed.json()[-1]['technician']['is_team_leader'] is True
    assert client.get(f"{URL}/{work_order['id']}").json()['status'] == 'APERTO'
    other = create(client)
    assert client.get(assignment_url(other)).json() == []


@pytest.mark.parametrize('body', [None, {}, {'rejection_notes': None}, {'rejection_notes': ''}])
def test_rejection_notes_are_optional(api, body):
    client, engine = api
    configure(engine)
    work_order = create(client)
    assignment = start(client, work_order)
    kwargs = {'json': body} if body is not None else {}
    response = client.post(f"/api/assignments/{assignment['id']}/reject", **kwargs)
    assert response.status_code == 200
    assert response.json()['rejection_notes'] == (body or {}).get('rejection_notes')


@pytest.mark.parametrize('initial_status', ['APERTO', 'IN_CORSO', 'EVASO'])
def test_accept_assignment_and_work_order_status_atomically(api, initial_status):
    client, engine = api
    configure(engine)
    work_order = create(client)
    for next_status in (['IN_CORSO', 'EVASO'] if initial_status == 'EVASO' else
                        ['IN_CORSO'] if initial_status == 'IN_CORSO' else []):
        assert client.patch(f"{URL}/{work_order['id']}/status", json={'status': next_status}).status_code == 200
    assignment = start(client, work_order)
    before = history(client, work_order)
    response = client.post(f"/api/assignments/{assignment['id']}/accept")
    assert response.status_code == 200
    accepted = response.json()
    assert accepted['status'] == 'ACCEPTED'
    assert datetime.fromisoformat(accepted['responded_at'])
    assert client.get(f"{URL}/{work_order['id']}").json()['status'] == 'IN_CORSO'
    assert client.get(f"{assignment_url(work_order)}/current").json() == accepted
    events = history(client, work_order)
    assert len(events) == len(before) + (1 if initial_status == 'IN_CORSO' else 2)
    assert 'ASSIGNMENT_ACCEPTED' in [item['event_type'] for item in events[:2]]
    if initial_status != 'IN_CORSO':
        assert events[0]['description'] == f'Stato ODL: {initial_status} → IN_CORSO'
    assert client.post(f"{assignment_url(work_order)}/start").status_code == 409
    for action in ('accept', 'reject', 'no-response'):
        assert client.post(f"/api/assignments/{assignment['id']}/{action}").status_code == 409
    assert history(client, work_order) == events


def test_duplicate_start_and_no_configuration(api):
    client, engine = api
    work_order = create(client)
    before = history(client, work_order)
    assert client.post(f"{assignment_url(work_order)}/start").status_code == 409
    assert history(client, work_order) == before
    configure(engine)
    assignment = start(client, work_order)
    before = history(client, work_order)
    assert client.post(f"{assignment_url(work_order)}/start").status_code == 409
    assert client.get(assignment_url(work_order)).json() == [assignment]
    assert history(client, work_order) == before


@pytest.mark.parametrize('action', ['reject', 'no-response'])
def test_exhausted_routing_preserves_previous_state_and_history(api, action):
    client, engine = api
    configure(engine, ((1, False),))
    work_order = create(client)
    assignment = start(client, work_order)
    before = history(client, work_order)
    response = client.post(f"/api/assignments/{assignment['id']}/{action}")
    assert response.status_code == 409
    assert 'Nessun tecnico successivo' in response.json()['detail']
    assert client.get(assignment_url(work_order)).json() == [assignment]
    assert history(client, work_order) == before
    # Configuration can be completed before retrying the same action.
    configure(engine, ((2, False),))
    assert client.post(f"/api/assignments/{assignment['id']}/{action}").status_code == 200
    assert client.get(f"{assignment_url(work_order)}/current").json()['attempt_number'] == 2


@pytest.mark.parametrize('with_pending', [False, True])
def test_direct_team_leader_escalation(api, with_pending):
    client, engine = api
    ids = configure(engine)
    work_order = create(client, priority='URGENTE')
    previous = start(client, work_order) if with_pending else None
    response = client.post(f"{assignment_url(work_order)}/escalate-team-leader")
    assert response.status_code == 201
    leader = response.json()
    assert leader['technician_id'] == ids[1]
    assert leader['status'] == 'PENDING'
    assert leader['attempt_number'] == (2 if with_pending else 1)
    events = history(client, work_order)
    assert events[0]['event_type'] == 'ASSIGNMENT_STARTED'
    assert events[1]['event_type'] == 'ASSIGNMENT_ESCALATED'
    if previous:
        replaced = client.get(assignment_url(work_order)).json()[0]
        assert replaced['id'] == previous['id']
        assert replaced['status'] == 'ESCALATED'
        assert replaced['responded_at'] is None
        assert client.post(f"/api/assignments/{previous['id']}/accept").status_code == 409
    for action in ('reject', 'no-response'):
        # Direct escalation must not loop back to skipped normal technicians.
        assert client.post(f"/api/assignments/{leader['id']}/{action}").status_code == 409
    assert client.post(f"{assignment_url(work_order)}/escalate-team-leader").status_code == 409
    assert history(client, work_order) == events
    assert client.get(f"{assignment_url(work_order)}/current").json() == leader


def test_no_leader_conflict_preserves_pending_assignment(api):
    client, engine = api
    configure(engine, ((1, False),))
    configure(engine, ((1, True),), category_id=2)
    work_order = create(client)
    assignment = start(client, work_order)
    before = history(client, work_order)
    assert client.post(f"{assignment_url(work_order)}/escalate-team-leader").status_code == 409
    assert client.get(assignment_url(work_order)).json() == [assignment]
    assert history(client, work_order) == before


def test_multiple_leaders_are_ordered_and_never_repeated(api):
    client, engine = api
    ids = configure(engine, ((9, True), (4, True)))
    work_order = create(client)
    first = start(client, work_order)
    assert first['technician_id'] == ids[4]
    assert client.post(f"/api/assignments/{first['id']}/no-response").status_code == 200
    second = client.get(f"{assignment_url(work_order)}/current").json()
    assert second['technician_id'] == ids[9]
    assert client.post(f"/api/assignments/{second['id']}/reject").status_code == 409


@pytest.mark.parametrize('action', ['start', 'escalate-team-leader', 'accept', 'reject', 'no-response'])
@pytest.mark.parametrize('terminal', ['CHIUSO', 'ANNULLATO'])
def test_terminal_work_orders_block_assignment_mutations(api, action, terminal):
    client, engine = api
    configure(engine)
    work_order = create(client)
    assignment = start(client, work_order)
    path = ['IN_CORSO', 'EVASO', 'CHIUSO'] if terminal == 'CHIUSO' else ['ANNULLATO']
    for next_status in path:
        assert client.patch(f"{URL}/{work_order['id']}/status", json={'status': next_status}).status_code == 200
    before = history(client, work_order)
    target = (f"{assignment_url(work_order)}/{action}" if action in {'start', 'escalate-team-leader'}
              else f"/api/assignments/{assignment['id']}/{action}")
    assert client.post(target).status_code == 409
    assert history(client, work_order) == before
    assert client.get(f"{assignment_url(work_order)}/current").json() == assignment


@pytest.mark.parametrize('method,path', [
    ('post', '/api/work-orders/999/assignments/start'),
    ('post', '/api/work-orders/999/assignments/escalate-team-leader'),
    ('get', '/api/work-orders/999/assignments/current'),
    ('get', '/api/work-orders/999/assignments'),
    ('post', '/api/assignments/999/accept'),
    ('post', '/api/assignments/999/reject'),
    ('post', '/api/assignments/999/no-response'),
])
def test_missing_resources(api, method, path):
    client, _ = api
    assert client.request(method, path).status_code == 404


@pytest.mark.parametrize('body', [{'reason': 'Guasto'}, {'rejection_notes': 42}, {'status': 'REJECTED'}])
def test_reject_payload_validation(api, body):
    client, engine = api
    configure(engine)
    work_order = create(client)
    assignment = start(client, work_order)
    before = history(client, work_order)
    assert client.post(f"/api/assignments/{assignment['id']}/reject", json=body).status_code == 422
    assert client.get(f"{assignment_url(work_order)}/current").json() == assignment
    assert history(client, work_order) == before


@pytest.mark.parametrize('action', ['start', 'accept', 'reject', 'no_response', 'escalate_team_leader'])
def test_history_storage_failure_rolls_back_assignment_operation(api, action):
    client, engine = api
    configure(engine)
    work_order = create(client)
    assignment = None if action == 'start' else start(client, work_order)
    before = client.get(assignment_url(work_order)).json()
    before_history = history(client, work_order)
    before_order = client.get(f"{URL}/{work_order['id']}").json()

    def fail_insert(mapper, connection, target):
        raise SQLAlchemyError('Simulated history failure')

    event.listen(WorkOrderHistory, 'before_insert', fail_insert)
    try:
        with Session(engine) as db:
            target_id = work_order['id'] if action in {'start', 'escalate_team_leader'} else assignment['id']
            with pytest.raises(SQLAlchemyError, match='Simulated history failure'):
                getattr(assignments, action)(db, target_id)
            assert db.is_active
            assert db.scalar(select(WorkOrder).where(WorkOrder.id == work_order['id'])).status.value == 'APERTO'
    finally:
        event.remove(WorkOrderHistory, 'before_insert', fail_insert)
    assert client.get(assignment_url(work_order)).json() == before
    assert history(client, work_order) == before_history
    assert client.get(f"{URL}/{work_order['id']}").json() == before_order


def test_stale_pending_assignment_is_reloaded_before_action(api):
    client, engine = api
    configure(engine)
    work_order = create(client)
    original = start(client, work_order)
    with Session(engine, expire_on_commit=False) as stale_db:
        stale = stale_db.get(Assignment, original['id'])
        stale_db.commit()
        assert client.post(f"/api/assignments/{original['id']}/accept").status_code == 200
        assert stale.status == AssignmentStatus.PENDING
        before = history(client, work_order)
        with pytest.raises(assignments.RoutingConflictError):
            assignments.reject(stale_db, original['id'])
    assert history(client, work_order) == before
    assert len(client.get(assignment_url(work_order)).json()) == 1
