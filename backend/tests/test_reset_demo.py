from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    AssignmentStatus,
    Category,
    Reminder,
    Technician,
    User,
    WorkOrder,
    WorkOrderHistory,
    WorkOrderNote,
)
from app.scripts import reset_demo as reset_demo_module
from app.scripts.reset_demo import main, reset_demo
from app.scripts.seed_demo import DEMO_CATEGORIES, DEMO_USER_EMAIL, seed_demo


def count(db: Session, model: type[object]) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def add_runtime_data(db: Session) -> tuple[WorkOrder, Technician]:
    requester_id = seed_demo(db)
    category = db.scalar(select(Category).where(Category.name == "Elettrico"))
    technician = db.scalar(select(Technician).where(Technician.category_id == category.id))
    technician.telegram_chat_id = "test-binding"
    work_order = WorkOrder(
        code="SOLVO-RESET-TEST", user_first_name="Demo", user_last_name="Utente",
        user_phone="123", fault_address="Via Demo 1", category_id=category.id,
        priority="MEDIA", description="Dato runtime da rimuovere",
    )
    db.add(work_order)
    db.flush()
    db.add_all([
        Assignment(work_order_id=work_order.id, technician_id=technician.id,
                   status=AssignmentStatus.PENDING, attempt_number=1),
        Reminder(work_order_id=work_order.id, created_by=requester_id, text="Promemoria"),
        WorkOrderHistory(work_order_id=work_order.id, event_type="CREATED", description="Creato"),
        WorkOrderNote(work_order_id=work_order.id, created_by=requester_id, text="Nota"),
    ])
    db.commit()
    return work_order, technician


def test_reset_command_refuses_without_confirmation():
    def unexpected_session() -> Session:
        raise AssertionError("La sessione non deve essere aperta senza --confirm")

    with pytest.raises(SystemExit, match="pass --confirm"):
        main([], session_factory=unexpected_session)


def test_reset_removes_runtime_data_preserves_bindings_and_reseeds(api):
    _, engine = api
    with Session(engine) as db:
        _, technician = add_runtime_data(db)
        binding_technician_id = technician.id
        counts = reset_demo(db)
        assert counts == {
            "assignments": 1,
            "reminders": 1,
            "work_order_history": 1,
            "work_order_notes": 1,
            "work_orders": 1,
            "categories": 13,
            "technicians": 52,
            "telegram_bindings_cleared": 0,
        }
        for model in (WorkOrder, Assignment, Reminder, WorkOrderHistory, WorkOrderNote):
            assert count(db, model) == 0
        assert count(db, Category) == len(DEMO_CATEGORIES)
        assert count(db, Technician) == 52
        assert db.scalar(select(User).where(User.email == DEMO_USER_EMAIL)) is not None
        assert db.get(Technician, binding_technician_id).telegram_chat_id == "test-binding"


def test_reset_can_clear_only_telegram_bindings(api):
    _, engine = api
    with Session(engine) as db:
        _, technician = add_runtime_data(db)
        technician_id = technician.id
        reset_demo(db, clear_telegram_bindings=True)
        reloaded = db.get(Technician, technician_id)
        assert reloaded.telegram_chat_id is None
        assert (reloaded.category_id, reloaded.escalation_order, reloaded.is_team_leader) == (1, 1, False)
        assert count(db, Technician) == 52


def test_reset_is_repeatable_and_restores_missing_reference_data(api):
    _, engine = api
    with Session(engine) as db:
        seed_demo(db)
        db.delete(db.scalar(select(Technician).where(Technician.email == "vetri.1@solvo-demo.example")))
        db.commit()
        first = reset_demo(db)
        second = reset_demo(db)
        assert first["technicians"] == second["technicians"] == 52
        assert first["categories"] == second["categories"] == 13
        assert count(db, WorkOrder) == 0


def test_reset_rolls_back_runtime_deletion_when_reseed_fails(api, monkeypatch):
    _, engine = api
    with Session(engine) as db:
        add_runtime_data(db)

        def fail_reseed(_db: Session, *, commit: bool = False) -> int:
            raise RuntimeError("seed failure")

        monkeypatch.setattr(reset_demo_module, "seed_demo", fail_reseed)
        with pytest.raises(RuntimeError, match="seed failure"):
            reset_demo(db)
        for model in (WorkOrder, Assignment, Reminder, WorkOrderHistory, WorkOrderNote):
            assert count(db, model) == 1
