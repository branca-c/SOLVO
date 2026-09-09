from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.assignments import Database, _api_errors
from app.core.config import Settings, get_settings
from app.schemas.assignment import AssignmentReject
from app.schemas.public_assignment import NotificationResponse, PublicAssignment
from app.services import assignments
from app.services.assignment_links import ActionLinkConfigurationError, InvalidActionTokenError, validate_token
from app.services.assignment_notifications import notify, public_details
from app.services.notifications import NotificationUnavailableError

router = APIRouter(prefix='/api', tags=['technician-actions'])
Configuration = Annotated[Settings, Depends(get_settings)]


@contextmanager
def action_errors() -> Iterator[None]:
    with _api_errors():
        try:
            yield
        except InvalidActionTokenError as exc:
            raise HTTPException(404, detail=str(exc), headers={'Cache-Control': 'no-store'}) from exc
        except (ActionLinkConfigurationError, NotificationUnavailableError) as exc:
            raise HTTPException(503, detail=str(exc), headers={'Cache-Control': 'no-store'}) from exc


def private_response(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'


@router.get('/public/assignments/{token}', response_model=PublicAssignment)
def get_assignment(token: str, db: Database, settings: Configuration, response: Response):
    private_response(response)
    with action_errors():
        return public_details(db, validate_token(token, settings))


@router.post('/public/assignments/{token}/accept', response_model=PublicAssignment)
def accept_assignment(token: str, db: Database, settings: Configuration, response: Response):
    private_response(response)
    with action_errors():
        assignment_id = validate_token(token, settings)
        assignments.accept(db, assignment_id)
        return public_details(db, assignment_id)


@router.post('/public/assignments/{token}/reject', response_model=PublicAssignment)
def reject_assignment(
    token: str, db: Database, settings: Configuration, response: Response,
    data: AssignmentReject | None = None,
):
    private_response(response)
    with action_errors():
        assignment_id = validate_token(token, settings)
        assignments.reject(db, assignment_id, data.rejection_notes if data else None)
        return public_details(db, assignment_id)


@router.post('/assignments/{assignment_id}/notify', response_model=NotificationResponse)
def notify_assignment(assignment_id: int, db: Database, settings: Configuration, response: Response):
    private_response(response)
    with action_errors():
        return notify(db, assignment_id, settings)
