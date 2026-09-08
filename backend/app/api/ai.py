from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.work_order_draft import WorkOrderDraft, WorkOrderDraftRequest
from app.services.ai.provider import AIProvider, AIProviderUnavailableError, create_provider
from app.services.work_order_drafts import InvalidAIOutputError, build_draft

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_ai_provider(settings: Annotated[Settings, Depends(get_settings)]) -> AIProvider:
    try:
        return create_provider(settings.ai_provider)
    except AIProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/work-order-draft", response_model=WorkOrderDraft)
def work_order_draft(
    data: WorkOrderDraftRequest,
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
) -> WorkOrderDraft:
    try:
        return build_draft(db, data.text, provider)
    except InvalidAIOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
