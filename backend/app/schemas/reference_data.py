from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


class TechnicianResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    email: str | None
    category_id: int
    category_name: str
    escalation_order: int
    is_team_leader: bool
