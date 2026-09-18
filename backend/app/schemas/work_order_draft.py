from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.email_addresses import valid_email
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

    @model_validator(mode="before")
    @classmethod
    def discard_invalid_optional_email(cls, data):
        if isinstance(data, dict) and isinstance(data.get("user_email"), str):
            if not valid_email(data["user_email"].strip()):
                data = dict(data)
                data["user_email"] = None
                warnings = data.get("warnings", [])
                if isinstance(warnings, list):
                    data["warnings"] = [
                        "Email non valida: inseriscila o correggila prima di confermare.",
                        *warnings[:9],
                    ]
        return data


class WorkOrderDraft(ExtractedWorkOrder):
    category_id: int | None = None
    description: str = Field(max_length=10000)


class AudioWorkOrderDraft(BaseModel):
    transcription_source: Literal["mock", "local_whisper"] | None = None
    transcript: str
    draft: WorkOrderDraft
