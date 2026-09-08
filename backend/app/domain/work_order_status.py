from app.models.enums import WorkOrderStatus

ALLOWED_TRANSITIONS = {
    WorkOrderStatus.APERTO: frozenset({WorkOrderStatus.IN_CORSO, WorkOrderStatus.ANNULLATO}),
    WorkOrderStatus.IN_CORSO: frozenset({WorkOrderStatus.EVASO, WorkOrderStatus.ANNULLATO}),
    WorkOrderStatus.EVASO: frozenset({WorkOrderStatus.CHIUSO, WorkOrderStatus.IN_CORSO}),
    WorkOrderStatus.CHIUSO: frozenset(),
    WorkOrderStatus.ANNULLATO: frozenset(),
}


class InvalidTransitionError(Exception):
    pass


def validate_transition(old: WorkOrderStatus, new: WorkOrderStatus) -> None:
    if old != new and new not in ALLOWED_TRANSITIONS[old]:
        raise InvalidTransitionError(f"Transizione non consentita: {old.value} → {new.value}")
