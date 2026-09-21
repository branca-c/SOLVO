from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.services.work_order_drafts import build_draft


class Provider:
    def __init__(self, description: str | None):
        self.description = description

    def extract(self, text, categories):
        return {"description": self.description}


def build_source_draft(source: str, provider_description: str | None):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        return build_draft(db, source, Provider(provider_description))


HEATING_REPORT = (
    "mi chiamo Chiara Branca abito in Via delle Magnolie, 25 a Catania, vorrei "
    "segnalare che da due giorni siamo al freddo, la temperatura è veramente bassa "
    "e lo stabile è abitato da gente anziana, chiedo intervento di manutenzione "
    "sull'impianto per mancanza di riscaldamento il prima possibile. per il "
    "sopralluogo contattatemi pure al 3286677356, oppure inviate una mail a "
    "chiara.branca1991@gmail.com. Grazie, saluti"
)


def test_ungrounded_heating_description_falls_back_to_source_terminology():
    draft = build_source_draft(HEATING_REPORT, "Perdita di riscaldamento nell'impianto.")

    assert "mancanza di riscaldamento" in draft.description.casefold()
    assert "perdita" not in draft.description.casefold()
    assert ". ." not in draft.description


def test_source_fallback_removes_identity_contacts_and_address():
    source = (
        "Mi chiamo Ada Rossi, telefono 3331234567, email ada.rossi@example.com. "
        "Il guasto è in Via Roma 20, Milano. Il tubo perde acqua."
    )
    draft = build_source_draft(source, "Perdita dal tubo.")

    description = draft.description.casefold()
    assert "ada" not in description
    assert "3331234567" not in description
    assert "example.com" not in description
    assert "via roma" not in description
    assert "il tubo perde acqua" in description


def test_sono_requester_identity_is_removed_before_fault_description():
    source = (
        "Sono Anna Bianchi. Telefono: 3471234567; Indirizzo: Via Libertà 85. "
        "Il climatizzatore perde acqua e non raffredda."
    )
    draft = build_source_draft(source, "Perdita d'acqua e mancato raffreddamento.")

    assert draft.description == "Il climatizzatore perde acqua e non raffredda."


def test_mi_chiamo_requester_identity_is_removed_before_fault_description():
    source = "Mi chiamo Ada Rossi. Il tubo perde acqua."
    draft = build_source_draft(source, "Perdita dal tubo.")

    assert draft.description == "Il tubo perde acqua."


def test_name_in_fault_context_is_not_removed_as_requester_identity():
    source = "Il climatizzatore di Anna Bianchi perde acqua."
    draft = build_source_draft(source, "Perdita d'acqua dal climatizzatore.")

    assert draft.description == source


def test_structured_contact_and_address_fields_are_removed_with_their_labels():
    source = (
        "Mi chiamo Ada Rossi. Telefono: +39 333 1234567; Email: ada@example.com; "
        "Indirizzo: Via Roma 12, Milano; C'è una perdita dal tubo del bagno."
    )
    draft = build_source_draft(source, "Guasto idraulico al bagno.")

    assert draft.description == "C'è una perdita dal tubo del bagno."


def test_grounded_provider_description_cannot_repeat_contact_or_address():
    source = "Il tubo perde acqua. Telefono 3331234567. Via Roma 20, Milano."
    provider_description = "Il tubo perde acqua. Telefono 3331234567. Via Roma 20, Milano."

    description = build_source_draft(source, provider_description).description.casefold()
    assert "3331234567" not in description
    assert "via roma" not in description
    assert "il tubo perde acqua" in description


def test_address_removal_does_not_leave_a_dangling_location_preposition():
    draft = build_source_draft("Guasto elettrico in Via Roma 12.", "Problema tecnico.")

    assert draft.description == "Guasto elettrico."


def test_address_removal_does_not_leave_a_dangling_fault_lead_in():
    source = "Il guasto è in Via Roma 12. Il tubo perde acqua."
    draft = build_source_draft(source, "Perdita dal tubo.")

    assert draft.description == "Il tubo perde acqua."


def test_invented_technical_diagnosis_is_rejected_for_source_fallback():
    draft = build_source_draft(
        "Il riscaldamento non funziona.",
        "Guasto alla caldaia con perdita di pressione.",
    )

    assert draft.description == "Il riscaldamento non funziona."
    assert "caldaia" not in draft.description.casefold()
    assert "perdita" not in draft.description.casefold()


def test_provider_description_with_only_source_terms_is_preserved():
    source = "Il climatizzatore perde acqua."
    description = "Il climatizzatore perde acqua."

    assert build_source_draft(source, description).description == description


def test_accepted_grounded_description_is_still_privacy_cleaned():
    source = (
        "Buongiorno, sono Chiara Branca. Ci sono delle persone bloccate in ascensore. "
        "Grazie."
    )
    description = (
        "Buongiorno, sono Chiara Branca. Ci sono delle persone bloccate in ascensore. "
        "Grazie."
    )

    assert build_source_draft(source, description).description == (
        "Ci sono delle persone bloccate in ascensore."
    )
