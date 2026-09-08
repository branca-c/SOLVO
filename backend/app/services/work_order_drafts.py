from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category
from app.schemas.work_order_draft import ExtractedWorkOrder, WorkOrderDraft
from app.services.ai.provider import AIProvider, AIProviderUnavailableError


class InvalidAIOutputError(Exception):
    pass


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def build_draft(db: Session, text: str, provider: AIProvider) -> WorkOrderDraft:
    try:
        raw = provider.extract(text)
    except Exception as exc:
        raise AIProviderUnavailableError("Analisi non disponibile. Riprova o usa l'inserimento manuale.") from exc
    try:
        extracted = ExtractedWorkOrder.model_validate(raw)
    except ValidationError as exc:
        raise InvalidAIOutputError("La bozza restituita non è valida. Usa l'inserimento manuale.") from exc

    values = extracted.model_dump()
    warnings = list(extracted.warnings)
    # Even a later model provider must not invent contact/address/name values.
    for field in ("user_first_name", "user_last_name", "user_phone", "user_email", "fault_address"):
        value = values[field]
        if value and _normalize(value) not in _normalize(text):
            values[field] = None
            warnings.append("Un dato non presente nel testo è stato escluso dalla bozza.")
    category_id = None
    values["category_name"] = None
    if extracted.category_name:
        matches = [category for category in db.scalars(select(Category))
                   if _normalize(category.name) == _normalize(extracted.category_name)]
        if len(matches) == 1:
            category_id = matches[0].id
            values["category_name"] = matches[0].name
        else:
            warnings.append("La categoria proposta non corrisponde a una categoria univoca configurata. Selezionala manualmente.")
    else:
        warnings.append("Categoria non individuata: selezionala manualmente.")
    if extracted.priority is None:
        warnings.append("Priorità non individuata: selezionala manualmente.")
    if any(values[field] is None for field in ("user_first_name", "user_last_name", "user_phone", "fault_address")):
        warnings.append("Completa i dati mancanti del richiedente e dell'indirizzo prima di confermare.")
    values["description"] = extracted.description or text
    values["warnings"] = list(dict.fromkeys(warnings))[:10]
    return WorkOrderDraft(**values, category_id=category_id)
