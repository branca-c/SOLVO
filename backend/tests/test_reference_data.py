import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Technician, User, UserRole, WorkOrder
from app.scripts.seed_demo import DEMO_CATEGORIES, DEMO_USER_EMAIL, seed_demo


def test_categories_read_only_and_ordered(api):
    client, _ = api
    assert client.get('/api/categories').json() == [
        {'id': 1, 'name': 'Elettrico', 'description': None},
        {'id': 2, 'name': 'Idraulico', 'description': None},
    ]
    assert client.post('/api/categories', json={'name': 'New'}).status_code == 405


def test_demo_seed_and_technician_api(api):
    client, engine = api
    with Session(engine) as db:
        user_id = seed_demo(db)
        first_ids = list(db.scalars(select(Technician.id).order_by(Technician.id)))
        assert seed_demo(db) == user_id
        assert list(db.scalars(select(Technician.id).order_by(Technician.id))) == first_ids
        assert db.scalar(select(func.count()).select_from(Category)) == 13
        assert db.scalar(select(func.count()).select_from(Technician)) == 52
        assert db.scalar(select(func.count()).select_from(WorkOrder)) == 0
        assert db.scalar(select(func.count()).select_from(User).where(User.email == DEMO_USER_EMAIL)) == 1
        assert db.get(User, user_id).role == UserRole.UTENTE
    categories = client.get('/api/categories').json()
    assert {item['name'] for item in categories} == set(DEMO_CATEGORIES)
    technicians = client.get('/api/technicians').json()
    assert len(technicians) == 52
    assert [item['category_name'] for item in technicians] == sorted(item['category_name'] for item in technicians)
    for category in categories:
        response = client.get('/api/technicians', params={'category_id': category['id']})
        assert response.status_code == 200
        chain = response.json()
        assert [item['escalation_order'] for item in chain] == [1, 2, 3, 4]
        assert [item['is_team_leader'] for item in chain] == [False, False, False, True]
        assert all(item['category_id'] == category['id'] and item['category_name'] == category['name'] for item in chain)
        assert all(item['phone'] and item['email'].endswith('@solvo-demo.example') for item in chain)
    assert client.get('/api/technicians?category_id=99999').json() == []
    assert client.get('/api/technicians?category_id=0').status_code == 422
    assert client.post('/api/technicians', json={}).status_code == 405
    created = client.post('/api/work-orders', json={
        'user_first_name': 'Demo', 'user_last_name': 'Demo', 'user_phone': '123',
        'fault_address': 'Demo', 'category_id': 1, 'priority': 'MEDIA', 'description': 'Demo',
    })
    assert created.status_code == 201
    assert client.post(f"/api/work-orders/{created.json()['id']}/reminders", json={'created_by': user_id}).status_code == 201


def test_seed_conflict_rolls_back_without_overwriting(api):
    _, engine = api
    with Session(engine) as db:
        db.add(Technician(first_name='Existing', last_name='Tech', phone='123',
                          category_id=1, escalation_order=1, is_team_leader=False))
        db.commit()
        with pytest.raises(ValueError, match='Posizione già configurata'):
            seed_demo(db)
        assert db.scalar(select(func.count()).select_from(Category)) == 2
        assert db.scalar(select(func.count()).select_from(Technician)) == 1
        assert db.scalar(select(Technician.first_name)) == 'Existing'
