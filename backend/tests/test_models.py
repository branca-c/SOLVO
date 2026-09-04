import pytest
from sqlalchemy.dialects import postgresql

from app.db.base import Base
from app.models import (
    Assignment,
    AssignmentStatus,
    Category,
    Priority,
    Reminder,
    Technician,
    User,
    UserRole,
    WorkOrder,
    WorkOrderHistory,
    WorkOrderStatus,
)


def test_domain_metadata_contains_expected_tables_and_foreign_keys() -> None:
    expected_tables = {
        "users",
        "categories",
        "technicians",
        "work_orders",
        "assignments",
        "reminders",
        "work_order_history",
    }

    assert set(Base.metadata.tables) == expected_tables
    assert next(iter(WorkOrder.__table__.c.category_id.foreign_keys)).target_fullname == "categories.id"
    assert next(iter(Assignment.__table__.c.work_order_id.foreign_keys)).target_fullname == "work_orders.id"
    assert next(iter(Assignment.__table__.c.technician_id.foreign_keys)).target_fullname == "technicians.id"
    assert next(iter(Reminder.__table__.c.created_by.foreign_keys)).target_fullname == "users.id"


def test_models_form_expected_relationship_graph() -> None:
    category = Category(name="Elettrico")
    technician = Technician(
        first_name="Ada",
        last_name="Rossi",
        phone="+390000000001",
        category=category,
        escalation_order=1,
        is_team_leader=False,
    )
    creator = User(
        first_name="Luca",
        last_name="Bianchi",
        phone="+390000000002",
        role=UserRole.UTENTE,
    )
    work_order = WorkOrder(
        code="ODL-0001",
        user_first_name="Luca",
        user_last_name="Bianchi",
        user_phone="+390000000002",
        fault_address="Via Roma 1",
        category=category,
        priority=Priority.MEDIA,
        description="Presa non funzionante",
        status=WorkOrderStatus.APERTO,
        reminders_count=1,
    )
    assignment = Assignment(
        work_order=work_order,
        technician=technician,
        status=AssignmentStatus.REJECTED,
        attempt_number=1,
        rejection_notes=None,
    )
    reminder = Reminder(work_order=work_order, creator=creator)
    history = WorkOrderHistory(
        work_order=work_order,
        event_type="CREATED",
        description="ODL creata",
    )

    assert assignment in work_order.assignments
    assert reminder in work_order.reminders
    assert history in work_order.history
    assert technician in category.technicians
    assert work_order in category.work_orders
    assert reminder in creator.reminders
    assert assignment.rejection_notes is None


@pytest.mark.parametrize(
    ("enum_class", "expected"),
    [
        (UserRole, ["UTENTE", "OPERATORE", "TECNICO"]),
        (Priority, ["PROGRAMMABILE", "BASSA", "MEDIA", "ALTA", "URGENTE"]),
        (WorkOrderStatus, ["APERTO", "IN_CORSO", "EVASO", "CHIUSO", "ANNULLATO"]),
        (
            AssignmentStatus,
            ["PENDING", "ACCEPTED", "REJECTED", "NO_RESPONSE", "ESCALATED"],
        ),
    ],
)
def test_enum_values_are_exact(enum_class: type, expected: list[str]) -> None:
    assert [member.value for member in enum_class] == expected


def test_sqlalchemy_enum_rejects_unknown_priority() -> None:
    processor = WorkOrder.__table__.c.priority.type.bind_processor(postgresql.dialect())

    assert processor is not None
    with pytest.raises(LookupError):
        processor("CRITICA")


def test_timestamps_and_counters_have_database_defaults() -> None:
    assert WorkOrder.__table__.c.created_at.server_default is not None
    assert WorkOrder.__table__.c.updated_at.server_default is not None
    assert WorkOrder.__table__.c.reminders_count.server_default is not None
    assert Assignment.__table__.c.sent_at.server_default is not None
    assert Reminder.__table__.c.created_at.server_default is not None
    assert WorkOrderHistory.__table__.c.created_at.server_default is not None
