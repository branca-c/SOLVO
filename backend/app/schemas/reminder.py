from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_by: int


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    created_at: datetime
    created_by: int
