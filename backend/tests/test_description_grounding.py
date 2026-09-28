import pytest

from app.domain.description_grounding import (
    postal_address_from_source,
    reconstruct_fault_quotes,
    reconstruct_selected_segments,
    segment_source,
    source_grounded_description,
)


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

SEGMENT_SOURCE = (
    "Introduzione.\n"
    "Problemi di rete al PC.\n"
    "Sito al piano 2° nell'aula n. 5 di ingegneria.\n"
    "Chiusura.\n"
    "Quinta nota."
)

MARIO_ROSSI_SOURCE = (
    "Buonasera, mi chiamo Mario Rossi, vorrei chiedere intervento di un tecnico "
    "all'Università di Palermo sita in Viale delle Scienze, 100 Palermo per problemi "
    "di rete al PC del Prof. Pelitteri, sito al piano 2° nell'aula n. 5 di ingegneria "
    "- tel. 3286677356 - mail mario.rossi@outlook.com. Cordiali saluti"
)


def test_source_segments_have_deterministic_ids_offsets_order_and_no_overlap():
    first = segment_source(SEGMENT_SOURCE)
    second = segment_source(SEGMENT_SOURCE)

    assert first == second
    assert [segment.id for segment in first] == ["S1", "S2", "S3", "S4", "S5"]
    assert [segment.text for segment in first] == [
        "Introduzione.",
        "Problemi di rete al PC.",
        "Sito al piano 2° nell'aula n. 5 di ingegneria.",
        "Chiusura.",
        "Quinta nota.",
    ]
    assert all(SEGMENT_SOURCE[segment.start:segment.end] == segment.text for segment in first)
    assert all(previous.end <= current.start for previous, current in zip(first, first[1:]))


def test_reconstruction_uses_only_issued_segments_in_source_order():
    segments = segment_source(SEGMENT_SOURCE)

    description = reconstruct_selected_segments(
        segments,
        ["S4", "S2", "S999", "IGNORE_PREVIOUS_INSTRUCTIONS", "S2"],
    )

    assert description == "Problemi di rete al PC. Chiusura."
    assert all(segment.text in SEGMENT_SOURCE for segment in (segments[1], segments[3]))
    assert "IGNORE_PREVIOUS_INSTRUCTIONS" not in description


def test_reconstruction_bounds_excessive_selection_in_source_order():
    segments = segment_source(SEGMENT_SOURCE)

    assert reconstruct_selected_segments(segments, [segment.id for segment in reversed(segments)]) == (
        "Introduzione. Problemi di rete al PC. "
        "Sito al piano 2° nell'aula n. 5 di ingegneria. Chiusura."
    )


@pytest.mark.parametrize(("source", "kwargs"), [
    ("tel. 3286677356", {}),
    ("mail mario.rossi@outlook.com", {}),
    ("Mario Rossi", {"requester_first_name": "Mario", "requester_last_name": "Rossi"}),
    ("Via Roma 25 a Palermo", {}),
])
def test_reconstruction_rejects_contact_identity_and_address_only_segments(source, kwargs):
    assert reconstruct_selected_segments(segment_source(source), ["S1"], **kwargs) == ""


@pytest.mark.parametrize(("source", "expected"), [
    ("Rottura vetro in Via delle Ginestre 25, Palermo.", "Via delle Ginestre 25, Palermo"),
    ("Il guasto è in Corso Italia 8.", "Corso Italia 8"),
    ("Intervento al secondo piano dell'appartamento.", None),
    ("Guasto tra Via Roma 12 e Piazza Verdi 5.", None),
])
def test_postal_address_fallback_uses_one_explicit_source_address_only(source, expected):
    assert postal_address_from_source(source) == expected


def test_operational_location_segment_remains_selectable_and_exact():
    source = "Sito al piano 2° nell'aula n. 5 di ingegneria"

    assert reconstruct_selected_segments(segment_source(source), ["S1"]) == source


def test_fault_quote_reconstruction_uses_exact_server_held_substrings_in_source_order():
    source = "Problemi di rete al PC. Sito al piano 2° nell'aula n. 5."
    segments = segment_source(source)

    assert reconstruct_fault_quotes(segments, [
        ("S2", "piano 2° nell'aula n. 5"),
        ("S1", "Problemi di rete"),
        ("S1", "Problemi di rete"),
    ]) == "Problemi di rete piano 2° nell'aula n. 5"


@pytest.mark.parametrize(("source", "quotes", "kwargs"), [
    ("Il server non risponde.", [("S1", "Guasto al cablaggio")], {}),
    ("Il server non risponde.", [("S999", "Il server non risponde")], {}),
    ("Mario Rossi.", [("S1", "Mario Rossi")], {
        "requester_first_name": "Mario", "requester_last_name": "Rossi",
    }),
    ("3286677356", [("S1", "3286677356")], {}),
    ("mario@example.com", [("S1", "mario@example.com")], {}),
    ("Via Roma 12", [("S1", "Via Roma 12")], {"fault_address": "Via Roma 12"}),
])
def test_fault_quote_reconstruction_rejects_ungrounded_or_unsafe_quotes(source, quotes, kwargs):
    assert reconstruct_fault_quotes(segment_source(source), quotes, **kwargs) == ""


def test_common_abbreviations_do_not_create_sentence_boundaries():
    source = "Problemi al PC del Prof. Pelitteri. Il guasto continua."

    assert [segment.text for segment in segment_source(source)] == [
        "Problemi al PC del Prof. Pelitteri.",
        "Il guasto continua.",
    ]


def test_true_sentence_ending_still_creates_a_boundary():
    source = "La rete non funziona. Il tecnico interviene domani."

    assert [segment.text for segment in segment_source(source)] == [
        "La rete non funziona.",
        "Il tecnico interviene domani.",
    ]


def test_long_comma_chained_report_splits_into_reasonably_sized_clauses():
    source = (
        "Prima clausola abbastanza lunga da rendere utile una separazione strutturale del report, "
        "seconda clausola altrettanto lunga con dettagli operativi indipendenti da selezionare, "
        "terza clausola lunga che completa la segnalazione senza usare regole semantiche."
    )

    segments = segment_source(source)

    assert [segment.text for segment in segments] == [
        "Prima clausola abbastanza lunga da rendere utile una separazione strutturale del report,",
        "seconda clausola altrettanto lunga con dettagli operativi indipendenti da selezionare,",
        "terza clausola lunga che completa la segnalazione senza usare regole semantiche.",
    ]
    assert all(source[segment.start:segment.end] == segment.text for segment in segments)
    assert all(previous.end <= current.start for previous, current in zip(segments, segments[1:]))
    assert segments == segment_source(source)


def test_short_comma_sentence_and_email_remain_intact():
    short_source = "Il PC è lento, ma resta utilizzabile."
    email_source = "Dettaglio tecnico molto lungo ma ancora unitario, mail mario.rossi@outlook.com, altro dettaglio lungo che completa il report senza una nuova frase."

    assert [segment.text for segment in segment_source(short_source)] == [short_source]
    assert any("mario.rossi@outlook.com" in segment.text for segment in segment_source(email_source))


def test_real_mario_source_segmentation_keeps_abbreviation_and_selectable_context():
    segments = segment_source(MARIO_ROSSI_SOURCE)

    assert [(segment.id, segment.text) for segment in segments] == [
        ("S1", "Buonasera, mi chiamo Mario Rossi,"),
        ("S2", "vorrei chiedere intervento di un tecnico all'Università di Palermo sita in Viale delle Scienze,"),
        ("S3", "100 Palermo per problemi di rete al PC del Prof. Pelitteri,"),
        ("S4", "sito al piano 2° nell'aula n. 5 di ingegneria"),
        ("S5", "tel. 3286677356"),
        ("S6", "mail mario.rossi@outlook.com."),
        ("S7", "Cordiali saluti"),
    ]
    assert reconstruct_selected_segments(segments, ["S4", "S3"]) == (
        "100 Palermo per problemi di rete al PC del Prof. Pelitteri, "
        "sito al piano 2° nell'aula n. 5 di ingegneria"
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
