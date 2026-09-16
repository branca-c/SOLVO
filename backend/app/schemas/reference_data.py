from pydantic import BaseModel, ConfigDict, model_validator
from app.schemas.work_order import Name, Phone, Email


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


class TechnicianUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    first_name: Name | None = None
    last_name: Name | None = None
    phone: Phone | None = None
    email: Email | None = None

    @model_validator(mode="after")
    def reject_null_required(self) -> "TechnicianUpdate":
        for field in self.model_fields_set - {"email"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} non può essere null")
        return self
