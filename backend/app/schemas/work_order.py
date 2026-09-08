from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Priority, WorkOrderStatus

Name = Annotated[str, Field(min_length=1, max_length=100)]
Phone = Annotated[str, Field(min_length=1, max_length=32)]
Email = Annotated[str, Field(max_length=255)]
Address = Annotated[str, Field(min_length=1, max_length=500)]
Description = Annotated[str, Field(min_length=1)]


class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_first_name: Name
    user_last_name: Name
    user_phone: Phone
    user_email: Email | None = None
    fault_address: Address
    category_id: int
    priority: Priority
    description: Description


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_first_name: Name | None = None
    user_last_name: Name | None = None
    user_phone: Phone | None = None
    user_email: Email | None = None
    fault_address: Address | None = None
    category_id: int | None = None
    priority: Priority | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "WorkOrderUpdate":
        for field in self.model_fields_set - {"user_email"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} non può essere null")
        return self


class WorkOrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: WorkOrderStatus


class WorkOrderResponse(WorkOrderCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_at: datetime
    updated_at: datetime
    status: WorkOrderStatus
    reminders_count: int
