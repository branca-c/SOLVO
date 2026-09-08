from collections.abc import Iterable
from typing import Protocol, TypeVar


class RoutingConflictError(Exception):
    pass


class RoutingTechnician(Protocol):
    id: int
    escalation_order: int
    is_team_leader: bool


T = TypeVar("T", bound=RoutingTechnician)


def select_technician(
    technicians: Iterable[T],
    attempted_ids: set[int],
    *,
    after_id: int | None = None,
    team_leader_only: bool = False,
) -> T:
    ordered = sorted(
        technicians, key=lambda technician: (
            technician.is_team_leader, technician.escalation_order, technician.id
        )
    )
    if after_id is not None:
        position = next((i for i, item in enumerate(ordered) if item.id == after_id), None)
        if position is None:
            raise RoutingConflictError("Il tecnico corrente non appartiene più alla categoria ODL")
        ordered = ordered[position + 1:]
    for technician in ordered:
        if technician.id not in attempted_ids and (
            not team_leader_only or technician.is_team_leader
        ):
            return technician
    if team_leader_only:
        raise RoutingConflictError("Nessun caposquadra non ancora tentato configurato per la categoria")
    raise RoutingConflictError("Nessun tecnico successivo non ancora tentato configurato per la categoria")
