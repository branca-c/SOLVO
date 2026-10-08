from sqlalchemy.orm import Session

from app.core.demo_access import DEMO_SESSION_GENERATION_INFO
from app.core.config import Settings
from app.models import Assignment
from app.schemas.public_assignment import NotificationResponse, PublicAssignment
from app.services import assignments
from app.services.assignment_links import action_url
from app.services.notifications import (
    NotificationUnavailableError,
    TelegramNotificationProvider,
    create_notification_provider,
)
from app.services import demo_sessions


def _telegram_destination(telegram_chat_id: str | None, demo_chat_id: str) -> str:
    """Prefer the assigned technician's private destination over the demo fallback."""
    destination = (telegram_chat_id or '').strip() or demo_chat_id.strip()
    if not destination:
        raise NotificationUnavailableError(
            'Destinazione Telegram non disponibile: collega il tecnico o configura TELEGRAM_DEMO_CHAT_ID.'
        )
    return destination


def public_details(db: Session, assignment_id: int) -> PublicAssignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise assignments.AssignmentResourceNotFoundError('Assegnazione non trovata')
    order = assignment.work_order
    technician = assignment.technician
    return PublicAssignment(
        id=assignment.id, status=assignment.status,
        technician_name=f'{technician.first_name} {technician.last_name}',
        work_order_code=order.code, requester_name=f'{order.user_first_name} {order.user_last_name}',
        requester_phone=order.user_phone, fault_address=order.fault_address,
        category=order.category.name, priority=order.priority, description=order.description,
        work_order_status=order.status, rejection_notes=assignment.rejection_notes,
    )


def _legacy_notify(
    db: Session, assignment_id: int, settings: Settings
) -> NotificationResponse:
    # Preserve the pre-demo-session transaction: the parent WorkOrder lock,
    # provider call, history write and commit all belong to one transaction.
    with assignments._transaction(db) as events:
        assignment, order, _ = assignments._action_target(db, assignment_id)
        url = action_url(assignment.id, settings)
        provider = create_notification_provider(settings)
        message = f'SOLVO — Nuovo intervento\nODL: {order.code}\nPriorità: {order.priority.value}\nIndirizzo: {order.fault_address}\nCategoria: {order.category.name}\nApri intervento: {url}'
        if isinstance(provider, TelegramNotificationProvider):
            destination = _telegram_destination(
                assignment.technician.telegram_chat_id, settings.telegram_demo_chat_id
            )
            result = provider.send(
                assignment.technician_id, message, destination=destination
            )
        else:
            result = provider.send(assignment.technician_id, message)
        assignments._history(
            db, order.id, 'ASSIGNMENT_NOTIFICATION_SENT',
            f'Assegnazione #{assignment.id}: notifica {result.provider}, {result.status}, riferimento {result.message_id}.',
        )
        events.append(('assignment.notification_sent', order.id))
    return NotificationResponse(
        provider=result.provider, message_id=result.message_id,
        status=result.status, action_url=url,
    )


def _demo_session_notify(
    db: Session, assignment_id: int, settings: Settings
) -> NotificationResponse:
    expected_generation = db.info.get(DEMO_SESSION_GENERATION_INFO)
    if expected_generation is None:
        raise demo_sessions.DemoSessionUnauthorizedError(
            'Sessione demo non valida o scaduta.'
        )

    # Phase one snapshots the real assignment and its destination while holding
    # the lifecycle lock. Roll back before provider I/O so release/acquire never
    # waits on an external Telegram request.
    try:
        demo_session = demo_sessions.require_generation(
            db, expected_generation, settings, lock=True
        )
        assignment, order, _ = assignments._action_target(db, assignment_id)
        url = action_url(assignment.id, settings)
        provider = create_notification_provider(settings)
        message = f'SOLVO — Nuovo intervento\nODL: {order.code}\nPriorità: {order.priority.value}\nIndirizzo: {order.fault_address}\nCategoria: {order.category.name}\nApri intervento: {url}'
        destination = (demo_session.telegram_chat_id or '').strip() or None
        if isinstance(provider, TelegramNotificationProvider) and destination is None:
            raise NotificationUnavailableError(
                'Telegram non collegato alla sessione demo.'
            )
        technician_id = assignment.technician_id
        work_order_id = order.id
        db.rollback()
    except Exception:
        db.rollback()
        raise

    result = (
        provider.send(technician_id, message, destination=destination)
        if destination is not None
        else provider.send(technician_id, message)
    )

    # Re-enter through the lifecycle lock before recording the side effect. If
    # release/acquire won while the provider call was in flight, generation A
    # cannot commit history into generation B.
    with assignments._transaction(db) as events:
        demo_sessions.require_generation(
            db, expected_generation, settings, lock=True
        )
        assignment, order, _ = assignments._action_target(db, assignment_id)
        assignments._history(
            db, order.id, 'ASSIGNMENT_NOTIFICATION_SENT',
            f'Assegnazione #{assignment.id}: notifica {result.provider}, {result.status}, riferimento {result.message_id}.',
        )
        events.append(('assignment.notification_sent', work_order_id))
    return NotificationResponse(
        provider=result.provider, message_id=result.message_id, status=result.status, action_url=url,
    )


def notify(db: Session, assignment_id: int, settings: Settings) -> NotificationResponse:
    if not settings.solvo_demo_session_enabled:
        return _legacy_notify(db, assignment_id, settings)
    return _demo_session_notify(db, assignment_id, settings)
