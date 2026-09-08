from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkOrderHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    event_type: str
    description: str
    created_at: datetime
