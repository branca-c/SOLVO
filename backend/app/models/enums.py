from enum import Enum


class UserRole(str, Enum):
    UTENTE = "UTENTE"
    OPERATORE = "OPERATORE"
    TECNICO = "TECNICO"


class Priority(str, Enum):
    PROGRAMMABILE = "PROGRAMMABILE"
    BASSA = "BASSA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


class WorkOrderStatus(str, Enum):
    APERTO = "APERTO"
    IN_CORSO = "IN_CORSO"
    EVASO = "EVASO"
    CHIUSO = "CHIUSO"
    ANNULLATO = "ANNULLATO"


class AssignmentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NO_RESPONSE = "NO_RESPONSE"
    ESCALATED = "ESCALATED"

