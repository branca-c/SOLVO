import pytest

from app.domain.description_grounding import source_grounded_description


REAL_AUDIO_SOURCE = (
    "Buongiorno, sono Chiara Branca e vorrei segnalare un guasto urgentissimo. "
    "Ci sono delle persone bloccate in ascensore nello stabile di via Roma 25 a Palermo. "
    "Il mio numero di telefono è 328 66 77 356. "
    "La mia mail è chiara.branca1991-gmail.com. Intervenite al più presto. Grazie."
)

REAL_AUDIO_START_ADDRESS_SOURCE = (
    "Sono Chiara Branca, vorrei segnalare un guasto urgentissimo. "
    "Nello stabile di via Roma 25 a Palermo ci sono delle persone bloccate in ascensore. "
    "Il mio numero di telefono è 328 66 77 356. "
    "La mia mail è chiara.branca1991-gmail.com. "
    "Vi prego di intervenire al più presto. Grazie."
)


def test_source_extractor_keeps_only_fault_from_real_audio_report():
    assert source_grounded_description(REAL_AUDIO_SOURCE) == (
        "Ci sono delle persone bloccate in ascensore."
    )


def test_source_extractor_keeps_fault_after_start_address_in_real_audio_report():
    assert source_grounded_description(REAL_AUDIO_START_ADDRESS_SOURCE) == (
        "Ci sono delle persone bloccate in ascensore."
    )


@pytest.mark.parametrize("introduction", [
    "Sono Mario Rossi.",
    "Mi chiamo Mario Rossi.",
    "Buongiorno, sono Mario Rossi.",
])
def test_source_extractor_removes_natural_requester_introductions(introduction):
    source = f"{introduction} Il cancello non si apre."

    assert source_grounded_description(source) == "Il cancello non si apre."


@pytest.mark.parametrize("contact", [
    "Il mio numero di telefono è 333 123 4567.",
    "Il mio telefono è 333 123 4567.",
    "Potete chiamarmi al 333 123 4567.",
    "Potete contattarmi al cel. 333 123 4567 oppure via mail a mario@test.com.",
    "La mia mail è mario.rossi.gmail.com.",
    "La mia email è mario.rossi.gmail.com.",
])
def test_source_extractor_removes_contact_variants(contact):
    source = f"Il cancello non si apre. {contact}"

    assert source_grounded_description(source) == "Il cancello non si apre."


@pytest.mark.parametrize("location", [
    "nello stabile di via Roma 25 a Palermo",
    "in via Roma 25, Palermo",
])
def test_source_extractor_removes_addresses_without_losing_surrounding_fault(location):
    source = f"L'ascensore è bloccato {location}. Le porte non si aprono."

    assert source_grounded_description(source) == "L'ascensore è bloccato. Le porte non si aprono."


def test_source_extractor_does_not_swallow_fault_after_address_locality():
    source = "Il guasto è in via Roma 25 a Palermo e l'ascensore non si muove."

    assert source_grounded_description(source) == "E l'ascensore non si muove."


@pytest.mark.parametrize("boilerplate", [
    "Vorrei segnalare che il cancello non si apre.",
    "Chiedo un intervento. Il cancello non si apre.",
    "Il cancello non si apre. Intervenite al più presto.",
    "Il cancello non si apre. Vi prego di intervenire al più presto.",
    "Il cancello non si apre. Contattatemi al più presto.",
    "Il cancello non si apre. Grazie, saluti.",
])
def test_source_extractor_removes_request_and_contact_boilerplate(boilerplate):
    assert source_grounded_description(boilerplate) == "Il cancello non si apre."


def test_source_extractor_preserves_multiple_fault_sentences_without_rewriting():
    source = "Il climatizzatore perde acqua. Non raffredda e fa un rumore forte."

    assert source_grounded_description(source) == source


def test_source_extractor_preserves_conjunction_inside_fault_description():
    source = "L'ascensore è bloccato e le porte non si aprono."

    assert source_grounded_description(source) == source


def test_source_extractor_returns_empty_when_source_contains_only_removable_material():
    source = "Buongiorno, sono Mario Rossi. Telefono: 333 123 4567. Grazie, saluti."

    assert source_grounded_description(source) == ""


def test_source_extractor_has_no_provider_summary_input():
    source = "Il cancello non si apre."
    provider_summary = "Guasto al sistema di apertura automatico."

    assert source_grounded_description(source) == "Il cancello non si apre."
    assert provider_summary not in source_grounded_description(source)
