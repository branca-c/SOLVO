from pydantic import BaseModel

from app.models.enums import AssignmentStatus, Priority, WorkOrderStatus


class PublicAssignment(BaseModel):
    id: int
    status: AssignmentStatus
    technician_name: str
    work_order_code: str
    requester_name: str
    requester_phone: str
    fault_address: str
    category: str
    priority: Priority
    description: str
    work_order_status: WorkOrderStatus
    rejection_notes: str | None


class NotificationResponse(BaseModel):
    provider: str
    message_id: str
    status: str
    action_url: str
