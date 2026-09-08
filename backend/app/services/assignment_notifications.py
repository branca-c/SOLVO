from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Assignment
from app.schemas.public_assignment import NotificationResponse, PublicAssignment
from app.services import assignments
from app.services.assignment_links import action_url
from app.services.whatsapp import create_whatsapp_provider


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


def notify(db: Session, assignment_id: int, settings: Settings) -> NotificationResponse:
    # Use the same parent lock and current-PENDING check as assignment actions.
    # HTTP submission cannot be rolled back if the subsequent database commit fails.
    with assignments._transaction(db):
        assignment, order, _ = assignments._action_target(db, assignment_id)
        url = action_url(assignment.id, settings)
        provider = create_whatsapp_provider(settings)
        message = f'SOLVO · {order.code}\nPriorità: {order.priority.value}\n{order.fault_address}\nCategoria: {order.category.name}\nApri intervento: {url}'
        result = provider.send(assignment.technician.phone, message)
        assignments._history(
            db, order.id, 'ASSIGNMENT_NOTIFICATION_SENT',
            f'Assegnazione #{assignment.id}: notifica {result.provider}, {result.status}, riferimento {result.message_id}.',
        )
    return NotificationResponse(
        provider=result.provider, message_id=result.message_id, status=result.status, action_url=url,
    )
