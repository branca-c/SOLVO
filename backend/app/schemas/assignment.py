from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AssignmentStatus


class AssignmentReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejection_notes: str | None = None


class TechnicianSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    phone: str
    email: str | None
    category_id: int
    escalation_order: int
    is_team_leader: bool


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    technician_id: int
    status: AssignmentStatus
    sent_at: datetime
    responded_at: datetime | None
    rejection_notes: str | None
    attempt_number: int
    technician: TechnicianSummary
