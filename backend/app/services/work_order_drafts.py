import re

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.draft_classification import category_fallback, normalize, reconcile_priority
from app.domain.description_grounding import (
    description_contains_separate_details, description_is_grounded, source_grounded_description,
)
from app.domain.email_addresses import audio_email_candidate, email_grounded
from app.models import Category
from app.services.timing import timed
from app.schemas.work_order_draft import ExtractedWorkOrder, WorkOrderDraft
from app.services.ai.provider import AIProvider, AIProviderUnavailableError, InvalidAIOutputError


INVALID_EMAIL_WARNING = "Email non valida: inseriscila o correggila prima di confermare."


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _grounded(field: str, value: str, text: str) -> bool:
    if field == "user_email":
        return email_grounded(value, text)
    if field == "user_phone":
        digits = re.sub(r"\D", "", value)
        pattern = r"(?<!\d)" + r"[\s()+.\-]*".join(digits) + r"(?!\d)"
        return bool(digits and re.search(pattern, text))

    def tokens(source: str) -> str:
        return " ".join(re.findall(r"\w+", source.casefold()))

    if field == "fault_address":
        # A city can be introduced by 'a/in' in speech and a comma in the form.
        parts = tokens(value).split()
        pattern = r"(?<!\w)" + r"(?:\s+(?:a|in)\s+|\s+)".join(
            re.escape(part) for part in parts
        ) + r"(?!\w)"
        return bool(parts and re.search(pattern, tokens(text)))
    return f" {tokens(value)} " in f" {tokens(text)} "


def build_draft(db: Session, text: str, provider: AIProvider, *, audio: bool = False) -> WorkOrderDraft:
    with timed("draft_extraction_total"):
        categories = list(db.scalars(select(Category).order_by(Category.name)))
        try:
            raw = provider.extract(text, [category.name for category in categories])
        except (AIProviderUnavailableError, InvalidAIOutputError):
            raise
        except Exception as exc:
            raise AIProviderUnavailableError("Analisi non disponibile. Riprova o usa l'inserimento manuale.") from exc
        try:
            extracted = ExtractedWorkOrder.model_validate(raw)
        except ValidationError as exc:
            raise InvalidAIOutputError("La bozza restituita non è valida. Usa l'inserimento manuale.") from exc

        values = extracted.model_dump()
        provider_warnings = list(extracted.warnings)
        warnings = list(provider_warnings)
        audio_email = audio_email_candidate(text) if audio else None
        if audio_email and values["user_email"] != audio_email:
            values["user_email"] = audio_email
            # The schema warning describes the provider's discarded invalid value,
            # which is no longer the value presented for review.
            provider_warnings = [
                warning for warning in provider_warnings if warning != INVALID_EMAIL_WARNING
            ]
            warnings = list(provider_warnings)
        if audio_email and (extracted.user_email != audio_email or not email_grounded(audio_email, text)):
            warnings.append("Email ricostruita dalla trascrizione audio: verifica prima di confermare.")
        # Even a later model provider must not invent contact/address/name values.
        for field in ("user_first_name", "user_last_name", "user_phone", "user_email", "fault_address"):
            value = values[field]
            # Permit harmless punctuation/spacing normalization (e.g. city commas).
            if value and not (field == "user_email" and value == audio_email) and not _grounded(field, value, text):
                values[field] = None
                warnings.append("Un dato non presente nel testo è stato escluso dalla bozza.")
        category_id = None
        values["category_name"] = None
        def resolve(name: str | None) -> Category | None:
            matches = [category for category in categories
                       if name and _normalize(category.name) == _normalize(name)]
            return matches[0] if len(matches) == 1 else None

        category = resolve(extracted.category_name)
        if category is None:
            proposal = category_fallback(text)
            matches = [item for item in categories
                       if proposal and normalize(item.name) == normalize(proposal)]
            category = matches[0] if len(matches) == 1 else None
            if category:
                warnings.append("Categoria proposta tramite regole deterministiche: verifica prima di confermare.")
        if category:
            category_id = category.id
            values["category_name"] = category.name
        elif extracted.category_name:
            warnings.append("La categoria proposta non corrisponde a una categoria univoca configurata. Selezionala manualmente.")
        else:
            warnings.append("Categoria non individuata: selezionala manualmente.")
        values["priority"] = reconcile_priority(text, extracted.priority)
        if values["priority"] != extracted.priority:
            warnings.append("Priorità proposta tramite regole deterministiche sul testo originale: verifica prima di confermare.")
        elif values["priority"] is None:
            warnings.append("Priorità non individuata: selezionala manualmente.")
        if any(values[field] is None for field in ("user_first_name", "user_last_name", "user_phone", "fault_address")):
            warnings.append("Completa i dati mancanti del richiedente e dell'indirizzo prima di confermare.")
        description = extracted.description or ""
        values["description"] = (
            description if not description or (
                description_is_grounded(text, description)
                and not description_contains_separate_details(description)
            )
            else source_grounded_description(text)
        )
        if not values["description"]:
            warnings.append("Descrizione tecnica non individuata: completala prima di confermare.")
        # Keep authoritative review warnings visible even if the model supplied ten.
        values["warnings"] = list(dict.fromkeys(
            warnings[len(provider_warnings):] + provider_warnings
        ))[:10]
        return WorkOrderDraft(**values, category_id=category_id)
