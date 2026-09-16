from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class WorkOrderNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1)

class WorkOrderNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    work_order_id: int
    text: str
    created_at: datetime
    created_by: int | None
