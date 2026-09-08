from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.assignment_routing import RoutingConflictError, select_technician
from app.domain.work_order_status import validate_transition
from app.models import (
    Assignment, AssignmentStatus, Technician, WorkOrder, WorkOrderHistory, WorkOrderStatus,
)


class AssignmentResourceNotFoundError(Exception):
    pass


@contextmanager
def _transaction(db: Session) -> Iterator[None]:
    # The service owns the transaction, including dependency/query autobegin.
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def _work_order(db: Session, work_order_id: int, *, lock: bool = False) -> WorkOrder:
    query = select(WorkOrder).where(WorkOrder.id == work_order_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    work_order = db.scalar(query)
    if work_order is None:
        raise AssignmentResourceNotFoundError("ODL non trovato")
    if lock and work_order.status in {WorkOrderStatus.CHIUSO, WorkOrderStatus.ANNULLATO}:
        raise RoutingConflictError("Non è possibile modificare assegnazioni di un ODL terminale")
    return work_order


def _attempts(db: Session, work_order_id: int) -> list[Assignment]:
    return list(db.scalars(
        select(Assignment)
        .options(joinedload(Assignment.technician))
        .where(Assignment.work_order_id == work_order_id)
        .order_by(Assignment.attempt_number, Assignment.id)
        .execution_options(populate_existing=True)
    ))


def _pending(attempts: list[Assignment]) -> Assignment | None:
    return next((item for item in reversed(attempts) if item.status == AssignmentStatus.PENDING), None)


def _candidate(
    db: Session, work_order: WorkOrder, attempts: list[Assignment],
    *, after_id: int | None = None, team_leader_only: bool = False,
) -> Technician:
    technicians = db.scalars(select(Technician).where(
        Technician.category_id == work_order.category_id
    )).all()
    return select_technician(
        technicians, {item.technician_id for item in attempts},
        after_id=after_id, team_leader_only=team_leader_only,
    )


def _history(db: Session, work_order_id: int, event_type: str, description: str) -> None:
    db.add(WorkOrderHistory(
        work_order_id=work_order_id, event_type=event_type, description=description
    ))


def _new_attempt(
    db: Session, work_order: WorkOrder, technician: Technician, attempt_number: int,
) -> Assignment:
    assignment = Assignment(
        work_order_id=work_order.id, technician=technician,
        status=AssignmentStatus.PENDING, attempt_number=attempt_number,
    )
    db.add(assignment)
    db.flush()
    _history(
        db, work_order.id, "ASSIGNMENT_STARTED",
        f"Assegnazione #{assignment.id}, tentativo {attempt_number}: tecnico #{technician.id}, PENDING",
    )
    return assignment


def start(db: Session, work_order_id: int) -> Assignment:
    with _transaction(db):
        work_order = _work_order(db, work_order_id, lock=True)
        attempts = _attempts(db, work_order.id)
        if _pending(attempts):
            raise RoutingConflictError("Esiste già un'assegnazione PENDING")
        if attempts:
            raise RoutingConflictError("Il routing è già stato avviato per questo ODL")
        technician = _candidate(db, work_order, attempts)
        assignment = _new_attempt(db, work_order, technician, 1)
    db.refresh(assignment)
    return assignment


def list_assignments(db: Session, work_order_id: int) -> list[Assignment]:
    _work_order(db, work_order_id)
    return _attempts(db, work_order_id)


def current(db: Session, work_order_id: int) -> Assignment:
    attempts = list_assignments(db, work_order_id)
    if not attempts:
        raise AssignmentResourceNotFoundError("Nessuna assegnazione per questo ODL")
    return _pending(attempts) or attempts[-1]


def _action_target(db: Session, assignment_id: int) -> tuple[Assignment, WorkOrder, list[Assignment]]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise AssignmentResourceNotFoundError("Assegnazione non trovata")
    # Lock the parent first for all actions, then reload assignments after waiting.
    work_order = _work_order(db, assignment.work_order_id, lock=True)
    attempts = _attempts(db, work_order.id)
    if assignment.status != AssignmentStatus.PENDING or assignment != attempts[-1]:
        raise RoutingConflictError("Solo l'assegnazione corrente PENDING può essere modificata")
    return assignment, work_order, attempts


def accept(db: Session, assignment_id: int) -> Assignment:
    with _transaction(db):
        assignment, work_order, _ = _action_target(db, assignment_id)
        old_status = work_order.status
        validate_transition(old_status, WorkOrderStatus.IN_CORSO)
        assignment.status = AssignmentStatus.ACCEPTED
        assignment.responded_at = datetime.now(timezone.utc)
        _history(
            db, work_order.id, "ASSIGNMENT_ACCEPTED",
            f"Assegnazione #{assignment.id} accettata dal tecnico #{assignment.technician_id}",
        )
        if old_status != WorkOrderStatus.IN_CORSO:
            work_order.status = WorkOrderStatus.IN_CORSO
            _history(
                db, work_order.id, "STATUS_CHANGED",
                f"Stato ODL: {old_status.value} → IN_CORSO",
            )
    db.refresh(assignment)
    return assignment


def _advance(
    db: Session, assignment_id: int, outcome: AssignmentStatus, rejection_notes: str | None = None,
) -> Assignment:
    with _transaction(db):
        assignment, work_order, attempts = _action_target(db, assignment_id)
        # Find a successor before changing anything; exhaustion leaves the prior state intact.
        technician = _candidate(db, work_order, attempts, after_id=assignment.technician_id)
        assignment.status = outcome
        assignment.responded_at = (
            datetime.now(timezone.utc) if outcome == AssignmentStatus.REJECTED else None
        )
        assignment.rejection_notes = rejection_notes
        description = f"Assegnazione #{assignment.id}, tecnico #{assignment.technician_id}: {outcome.value}"
        if rejection_notes is not None:
            description += f". Note: {rejection_notes}"
        _history(db, work_order.id, f"ASSIGNMENT_{outcome.value}", description)
        _new_attempt(db, work_order, technician, assignment.attempt_number + 1)
    db.refresh(assignment)
    return assignment


def reject(db: Session, assignment_id: int, rejection_notes: str | None = None) -> Assignment:
    return _advance(db, assignment_id, AssignmentStatus.REJECTED, rejection_notes)


def no_response(db: Session, assignment_id: int) -> Assignment:
    return _advance(db, assignment_id, AssignmentStatus.NO_RESPONSE)


def escalate_team_leader(db: Session, work_order_id: int) -> Assignment:
    with _transaction(db):
        work_order = _work_order(db, work_order_id, lock=True)
        attempts = _attempts(db, work_order.id)
        technician = _candidate(db, work_order, attempts, team_leader_only=True)
        active = _pending(attempts)
        if active is not None:
            active.status = AssignmentStatus.ESCALATED
            # Escalation is an operator action, not a technician response.
            active.responded_at = None
        _history(
            db, work_order.id, "ASSIGNMENT_ESCALATED",
            f"Escalation diretta al caposquadra #{technician.id}"
            + (f"; assegnazione #{active.id} sostituita: ESCALATED" if active else ""),
        )
        number = attempts[-1].attempt_number + 1 if attempts else 1
        assignment = _new_attempt(db, work_order, technician, number)
    db.refresh(assignment)
    return assignment
