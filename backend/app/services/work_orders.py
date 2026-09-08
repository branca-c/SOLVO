from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Priority, WorkOrder, WorkOrderHistory, WorkOrderStatus
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
    db.commit()
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
    for field, value in changes.items():
        setattr(work_order, field, value)
    db.commit()
    db.refresh(work_order)
    return work_order


def change_status(db: Session, work_order: WorkOrder, status: WorkOrderStatus) -> WorkOrder:
    if work_order.status != status:
        db.add(WorkOrderHistory(
            work_order_id=work_order.id,
            event_type="STATUS_CHANGED",
            description=f"Stato ODL: {work_order.status.value} → {status.value}",
        ))
        work_order.status = status
        db.commit()
        db.refresh(work_order)
    return work_order


def delete(db: Session, work_order: WorkOrder) -> None:
    db.delete(work_order)
    db.commit()
