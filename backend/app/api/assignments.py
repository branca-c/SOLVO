from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.assignment_routing import RoutingConflictError
from app.models import Assignment
from app.schemas.assignment import AssignmentReject, AssignmentResponse
from app.services import assignments

router = APIRouter(prefix="/api", tags=["assignments"])
Database = Annotated[Session, Depends(get_db)]


@contextmanager
def _api_errors() -> Iterator[None]:
    try:
        yield
    except assignments.AssignmentResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RoutingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/work-orders/{work_order_id}/assignments/start",
    response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED,
)
def start_assignment(work_order_id: int, db: Database) -> Assignment:
    with _api_errors():
        return assignments.start(db, work_order_id)


@router.get("/work-orders/{work_order_id}/assignments/current", response_model=AssignmentResponse)
def current_assignment(work_order_id: int, db: Database) -> Assignment:
    with _api_errors():
        return assignments.current(db, work_order_id)


@router.get("/work-orders/{work_order_id}/assignments", response_model=list[AssignmentResponse])
def list_assignments(work_order_id: int, db: Database) -> list[Assignment]:
    with _api_errors():
        return assignments.list_assignments(db, work_order_id)


@router.post("/assignments/{assignment_id}/accept", response_model=AssignmentResponse)
def accept_assignment(assignment_id: int, db: Database) -> Assignment:
    with _api_errors():
        return assignments.accept(db, assignment_id)


@router.post("/assignments/{assignment_id}/reject", response_model=AssignmentResponse)
def reject_assignment(
    assignment_id: int, db: Database, data: AssignmentReject | None = None,
) -> Assignment:
    with _api_errors():
        return assignments.reject(db, assignment_id, data.rejection_notes if data else None)


@router.post("/assignments/{assignment_id}/no-response", response_model=AssignmentResponse)
def no_response_assignment(assignment_id: int, db: Database) -> Assignment:
    with _api_errors():
        return assignments.no_response(db, assignment_id)


@router.post(
    "/work-orders/{work_order_id}/assignments/escalate-team-leader",
    response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED,
)
def escalate_team_leader(work_order_id: int, db: Database) -> Assignment:
    with _api_errors():
        return assignments.escalate_team_leader(db, work_order_id)
