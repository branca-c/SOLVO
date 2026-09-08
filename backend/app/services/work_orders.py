from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update as sql_update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.work_order_status import InvalidTransitionError, validate_transition
from app.models import Category, Priority, Reminder, User, WorkOrder, WorkOrderHistory, WorkOrderStatus
from app.services.realtime import publish
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate


class InvalidCategoryError(Exception):
    pass


def validate_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise InvalidCategoryError("Categoria non trovata")


def create(db: Session, data: WorkOrderCreate) -> WorkOrder:
    validate_category(db, data.category_id)
    code = f"SOLVO-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:16].upper()}"
    work_order = WorkOrder(
        **data.model_dump(), code=code, status=WorkOrderStatus.APERTO, reminders_count=0
    )
    work_order.history.append(
        WorkOrderHistory(event_type="CREATED", description="ODL creata: APERTO")
    )
    db.add(work_order)
    db.flush()
    order_id = work_order.id
    db.commit()
    publish('work_order.created', order_id)
    db.refresh(work_order)
    return work_order


def list_work_orders(
    db: Session,
    status: WorkOrderStatus | None = None,
    priority: Priority | None = None,
    category_id: int | None = None,
) -> list[WorkOrder]:
    query = select(WorkOrder)
    if status is not None:
        query = query.where(WorkOrder.status == status)
    if priority is not None:
        query = query.where(WorkOrder.priority == priority)
    if category_id is not None:
        query = query.where(WorkOrder.category_id == category_id)
    return list(db.scalars(query.order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())))


def update(db: Session, work_order: WorkOrder, data: WorkOrderUpdate) -> WorkOrder:
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        validate_category(db, changes["category_id"])
    changed = any(getattr(work_order, field) != value for field, value in changes.items())
    order_id = work_order.id
    for field, value in changes.items():
        setattr(work_order, field, value)
    db.commit()
    if changed:
        publish('work_order.updated', order_id)
    db.refresh(work_order)
    return work_order


def change_status(db: Session, work_order: WorkOrder, status: WorkOrderStatus) -> WorkOrder:
    try:
        # Reload and lock the current row before checking its status (PostgreSQL).
        db.refresh(work_order, with_for_update=True)
        validate_transition(work_order.status, status)
        changed = work_order.status != status
        order_id = work_order.id
        if changed:
            db.add(WorkOrderHistory(
                work_order_id=work_order.id,
                event_type="STATUS_CHANGED",
                description=f"Stato ODL: {work_order.status.value} → {status.value}",
            ))
            work_order.status = status
        db.commit()
    except (SQLAlchemyError, InvalidTransitionError):
        db.rollback()
        raise
    if changed:
        publish('work_order.status_changed', order_id)
    db.refresh(work_order)
    return work_order


class InvalidReminderCreatorError(Exception):
    pass


def create_reminder(db: Session, work_order: WorkOrder, created_by: int) -> Reminder:
    if db.get(User, created_by) is None:
        raise InvalidReminderCreatorError("Utente del sollecito non trovato")
    order_id = work_order.id
    reminder = Reminder(work_order_id=order_id, created_by=created_by)
    try:
        # Increment in SQL, never from a potentially stale in-memory counter.
        db.execute(
            sql_update(WorkOrder)
            .where(WorkOrder.id == work_order.id)
            .values(reminders_count=WorkOrder.reminders_count + 1)
        )
        db.add(reminder)
        db.flush()
        db.add(WorkOrderHistory(
            work_order_id=work_order.id,
            event_type="REMINDER_CREATED",
            description=f"Sollecito #{reminder.id} creato dall'utente #{created_by}",
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    publish('reminder.created', order_id)
    db.refresh(reminder)
    return reminder


def list_reminders(db: Session, work_order: WorkOrder) -> list[Reminder]:
    return list(db.scalars(
        select(Reminder)
        .where(Reminder.work_order_id == work_order.id)
        .order_by(Reminder.created_at.desc(), Reminder.id.desc())
    ))


def list_history(db: Session, work_order: WorkOrder) -> list[WorkOrderHistory]:
    return list(db.scalars(
        select(WorkOrderHistory)
        .where(WorkOrderHistory.work_order_id == work_order.id)
        .order_by(WorkOrderHistory.created_at.desc(), WorkOrderHistory.id.desc())
    ))


def delete(db: Session, work_order: WorkOrder) -> None:
    order_id = work_order.id
    db.delete(work_order)
    db.commit()
    publish('work_order.deleted', order_id)
