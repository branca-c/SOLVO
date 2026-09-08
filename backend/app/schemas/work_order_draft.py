from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Priority
from app.schemas.work_order import Address, Email, Name, Phone


class WorkOrderDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=10000)


class ExtractedWorkOrder(BaseModel):
    """Provider contract: no IDs, workflow fields, or persistence commands."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_first_name: Name | None = None
    user_last_name: Name | None = None
    user_phone: Phone | None = None
    user_email: Email | None = None
    fault_address: Address | None = None
    category_name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    priority: Priority | None = None
    description: Annotated[str, Field(max_length=10000)] | None = None
    warnings: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=10
    )


class WorkOrderDraft(ExtractedWorkOrder):
    category_id: int | None = None
    description: str = Field(min_length=1, max_length=10000)
