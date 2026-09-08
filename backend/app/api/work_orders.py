from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Priority, Reminder, WorkOrder, WorkOrderHistory, WorkOrderStatus
from app.schemas.reminder import ReminderCreate, ReminderResponse
from app.schemas.work_order_history import WorkOrderHistoryResponse
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderResponse,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)
from app.services import work_orders

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])
Database = Annotated[Session, Depends(get_db)]


def get_work_order(work_order_id: int, db: Database) -> WorkOrder:
    work_order = db.get(WorkOrder, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="ODL non trovato")
    return work_order


ExistingWorkOrder = Annotated[WorkOrder, Depends(get_work_order)]


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order(data: WorkOrderCreate, db: Database) -> WorkOrder:
    try:
        return work_orders.create(db, data)
    except work_orders.InvalidCategoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[WorkOrderResponse])
def list_work_orders(
    db: Database,
    status: WorkOrderStatus | None = None,
    priority: Priority | None = None,
    category_id: int | None = None,
) -> list[WorkOrder]:
    return work_orders.list_work_orders(db, status, priority, category_id)


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def read_work_order(work_order: ExistingWorkOrder) -> WorkOrder:
    return work_order


@router.patch("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order(
    data: WorkOrderUpdate, work_order: ExistingWorkOrder, db: Database
) -> WorkOrder:
    try:
        return work_orders.update(db, work_order, data)
    except work_orders.InvalidCategoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{work_order_id}/status", response_model=WorkOrderResponse)
def change_work_order_status(
    data: WorkOrderStatusUpdate, work_order: ExistingWorkOrder, db: Database
) -> WorkOrder:
    try:
        return work_orders.change_status(db, work_order, data.status)
    except work_orders.InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_order(work_order: ExistingWorkOrder, db: Database) -> Response:
    work_orders.delete(db, work_order)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{work_order_id}/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    data: ReminderCreate, work_order: ExistingWorkOrder, db: Database
) -> Reminder:
    try:
        return work_orders.create_reminder(db, work_order, data.created_by)
    except work_orders.InvalidReminderCreatorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{work_order_id}/reminders", response_model=list[ReminderResponse])
def list_reminders(work_order: ExistingWorkOrder, db: Database) -> list[Reminder]:
    return work_orders.list_reminders(db, work_order)


@router.get("/{work_order_id}/history", response_model=list[WorkOrderHistoryResponse])
def list_history(work_order: ExistingWorkOrder, db: Database) -> list[WorkOrderHistory]:
    return work_orders.list_history(db, work_order)
