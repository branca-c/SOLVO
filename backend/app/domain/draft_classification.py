"""Conservative lexical proposals; no provider, HTTP or database access."""
import re

from app.models.enums import Priority

# Labels identify configurable category names, never IDs or a category enum.
CATEGORY_SIGNALS = {
    "Ascensore": r"ascensor[ei]|elevator[ei]",
    "Idraulico": r"perdita (?:d )?acqua|tub[oi]|rubinett[oi]|lavandin[oi]|scarico|scarichi|sifon[ei]|allagament[oi]",
    "Climatizzazione": r"climatizzator[ei]|condizionator[ei]|aria condizionata|split",
    "Riscaldamento": r"termosifon[ei]|caldai[ae]|riscaldamento|calorifer[oi]",
    "Elettrico": r"corrente|pres[ae] elettrich?[ae]|interruttor[ei]|quadr[oi] elettric[oi]|corto circuito|cortocircuito",
    "Rete": r"rete|internet|connession[ei]|wi fi|wifi",
    "Vetri": r"vetr[oi]|vetrat[ae]",
    "Serramenti": r"port[ae]|finestr[ae]|serratur[ae]|infiss[oi]",
    "Edile": r"mur[oi]|soffitt[oi]|intonac[oi]|paviment[oi]|crep[ae]",
    "Antincendio": r"estintor[ei]|antincendio|rilevator[ei] (?:di )?fumo",
    "Sicurezza": r"allarm[ei]|videosorveglianza|telecamer[ae]",
    "Arredi": r"mobil[ei]|scrivani[ae]|sedi[ae]|armadi[oi]",
}


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def _clauses(text: str) -> list[str]:
    # Remove paired quotes (not apostrophes in l'ascensore/d'acqua) and examples.
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|«[^»\n]*»|(?<!\w)\x27[^\x27\n]+\x27(?!\w)', ' ', text)
    return [normalize(part) for part in re.split(
        r"[.;!?\n]|\b(?:ma|però|invece)\b", text.casefold()
    ) if not re.search(r"\b(?:esempio|ipoteticamente|supponiamo)\b", part)]


def _positive(pattern: str, clause: str) -> bool:
    for match in re.finditer(r"\b(?:" + pattern + r")\b", clause):
        prefix = clause[:match.start()]
        if not re.search(r"\b(?:non|nessun[oa]?|senza|assenza di)\b", prefix):
            return True
    return False


def category_fallback(text: str) -> str | None:
    clauses = _clauses(text)
    supported = [name for name, pattern in CATEGORY_SIGNALS.items()
                 if any(_positive(pattern, clause) for clause in clauses)]
    # Consider competing signals even if a competing category is not configured.
    return supported[0] if len(supported) == 1 else None


def _priority_clauses(text: str) -> list[str]:
    """Use report evidence, excluding recognizable contact/location spans."""
    # Also remove a conventionally capitalized locality after an address comma.
    text = re.sub(
        r"\b(?i:via|viale|corso|piazza|vicolo|largo)\s+[^,.;!?:\n]+"
        r"(?:,\s*[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2}"
        r"(?:\s*\([A-Z]{2}\)|,\s*[A-Z]{2}\b)?(?=\s*[,.;!?]|\s*$))?",
        " ", text,
    )
    text = re.sub(
        r"\b(?i:sono)\s+[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2}"
        r"(?=\s*[,.;]|\s*$|\s+(?i:telefono|vorrei|segnalo|il guasto|ho)\b)",
        " ", text,
    )
    text = text.casefold()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", " ", text)
    text = re.sub(r"\+?\d[\d\s().-]{5,}\d", " ", text)
    text = re.sub(
        r"\b(?:mi chiamo|nome(?: e cognome)?\s*:)\s+"
        r"[a-zà-ÿ]+(?:\s+[a-zà-ÿ]+){0,2}"
        r"(?=\s*[,.;]|\s*$|\s+(?:telefono|vorrei|segnalo|il guasto|ho)\b)",
        " ", text,
    )
    # Street/place names can contain severity words (e.g. via del Fumo).
    text = re.sub(
        r"\b(?:via|viale|corso|piazza|vicolo|largo)\s+[^,.;!?:\n]+",
        " ", text,
    )
    text = re.sub(r"\b(?:indirizzo|località|città|provincia|cap)\s*:[^,.;!?:\n]+", " ", text)
    # A wrapped sentence is still one report, not separate evidence clauses.
    return _clauses(text.replace("\n", " ").replace(",", ";"))


def _priority_positive(pattern: str, clause: str) -> bool:
    for match in re.finditer(r"\b(?:" + pattern + r")\b", clause):
        # Reset negation only for an independent report after a conjunction.
        # 'Non ci sono scintille e cavi scoperti' negates both danger signals.
        prefix = re.split(
            r"\b(?:e|mentre)\b(?=\s+(?:ci sono|c è|(?:il |la |l )?"
            r"(?:condizionatore|climatizzatore|riscaldamento|ascensore|rubinetto|porta|internet|rete|presa|acqua)\b))",
            clause[:match.start()],
        )[-1]
        if match.group().startswith("non ") and re.match(r"\s+(?:male|peggio)\b", clause[match.end():]):
            continue
        if not re.search(r"\b(?:non|nessun[oa]?|senza|assenza di|nessun rischio di)\b", prefix):
            return True
    return False


def _complete_heating_outage(clauses: list[str]) -> bool:
    """Recognize bounded wording that states heating service is wholly unavailable."""
    partial = any(re.search(
        r"\briscaldamento\b[^.;!?]*\b(?:solo|parzialmente|in alcune|in una)\b",
        clause,
    ) for clause in clauses)
    if partial:
        return False
    total_loss = (
        r"mancanza di riscaldamento|senza riscaldamento|non c è riscaldamento"
        r"|riscaldamento non funziona|riscaldamento (?:è )?completamente assente"
    )
    if any(_priority_positive(total_loss, clause) for clause in clauses):
        return True
    return (
        any(_priority_positive(r"(?:siamo|sono) al freddo", clause) for clause in clauses)
        and any(_priority_positive(r"riscaldamento|impianto", clause) for clause in clauses)
    )


def priority_fallback(text: str) -> Priority | None:
    clauses = _priority_clauses(text)
    danger = (
        r"(?:persona|persone|qualcuno) (?:è |sono )?(?:bloccata|bloccate|bloccato|bloccati|intrappolata|intrappolate|intrappolato|intrappolati)"
        r"|incendio|fumo"
        r"|fuga di gas|odore forte di gas|forte odore di gas"
        r"|cavi scoperti|scintille|(?:grave )?rischio elettrico"
        r"|rischio immediato(?: per (?:le )?(?:persone|cose|beni))?"
        r"|pericolo immediato|rischio per (?:le )?persone"
        r"|pericolo per (?:la sicurezza delle |le )persone|emergenza (?:in corso|immediata)"
        r"|grave allagamento"
    )
    for clause in clauses:
        # A smoke detector is equipment, not evidence that smoke is present.
        danger_clause = re.sub(r"(?:rilevator[ei]|sensor[ei]) (?:di )?fumo", "sensore", clause)
        if _priority_positive(danger, danger_clause):
            return Priority.URGENTE
        if (_priority_positive(r"forte perdita|allagamento|acqua", clause)
                and _priority_positive(r"danni immediati|rischio (?:di )?danni immediati", clause)):
            return Priority.URGENTE
    if _complete_heating_outage(clauses):
        return Priority.ALTA
    for clause in clauses:
        if (_priority_positive(r"ascensor[ei]|elevator[ei]", clause)
                and (_priority_positive(r"bloccato|bloccati|fermo|fuori servizio", clause)
                     or _priority_positive(r"non (?:riparte|ripartono)", clause))):
            return Priority.ALTA
        if _priority_positive(r"interruzione totale|blackout totale|servizio completamente interrotto", clause):
            return Priority.ALTA
        if (re.search(r"\b(?:riscaldamento|rete|internet)\b", clause)
                and _priority_positive(r"(?:completamente|totalmente) (?:assente|bloccato|inutilizzabile|interrotto)", clause)):
            return Priority.ALTA
        if _priority_positive(
            r"(?:tutto l edificio|intero edificio|tutto il palazzo|intero palazzo) "
            r"(?:è )?senza (?:riscaldamento|corrente|internet|rete)", clause,
        ):
            return Priority.ALTA
        if _priority_positive(
            r"(?:guasto|malfunzionamento) (?:(?:grave|importante) )?"
            r"(?:che )?(?:impedisce|blocca) (?:completamente )?(?:il normale uso|l uso normale|l utilizzo|l uso)",
            clause,
        ):
            return Priority.ALTA

    minor = r"piccolo inconveniente|piccolo fastidio|disagio minore|lieve malfunzionamento"
    cosmetic = r"(?:piccolo|lieve|minimo) (?:difetto estetico|graffio|difetto cosmetico)|(?:lieve|piccolo) rumore"
    usable_defect = (
        r"(?:piccolo|lieve|minimo) (?:difetto|deterioramento)|componente (?:allentato|non critico)"
    )
    usable = r"(?:ancora |comunque )?(?:utilizzabile|usabile)|funziona ancora|ancora funzionante"
    still_usable = any(_priority_positive(usable, clause) for clause in clauses)
    minor_clauses = [
        _priority_positive(minor + "|" + cosmetic, clause)
        or (_priority_positive(usable_defect, clause) and still_usable)
        for clause in clauses
    ]
    # Remove only the mild phrase itself; a separate concrete failure still wins.
    for clause, is_minor in zip(clauses, minor_clauses):
        active_clause = re.sub(r"\b(?:" + minor + r")\b", " ", clause) if is_minor else clause
        if (_priority_positive(
            r"guast[oaie]|malfunzionament[oi]|rott[oaie]|perdita|perde(?: acqua)?|gocciola"
            r"|non (?:funzionante|funzionanti|funziona|funzionano|raffredda|raffreddano|scarica|si apre|si chiude)"
            r"|non (?:utilizzabile|usabile)|inutilizzabile"
            r"|(?:riscaldamento|condizionatore|rete|internet) (?:è )?(?:assente|fuori servizio)",
            active_clause,
        )):
            return Priority.MEDIA
    if any(minor_clauses):
        return Priority.BASSA
    if any(_priority_positive(
        r"controllo periodico|manutenzione (?:programmata|preventiva)|intervento pianificato"
        r"|sostituzione preventiva|verniciatura|regolazione non urgente|programmabile", clause,
    ) for clause in clauses):
        return Priority.PROGRAMMABILE
    return None


def _unambiguous_blockage(clauses: list[str]) -> bool:
    """Only downgrade URGENTE for a narrowly understood report.

    Unknown residual wording may explain the provider's urgency. Absence of a
    recognized danger keyword alone is not evidence that the report is safe.
    """
    blockage = (
        r"(?:(?:l |il |gli )?(?:ascensor[ei]|elevator[ei]) (?:è |sono )?"
        r"(?:bloccato|bloccati|fermo|fuori servizio|non riparte|non ripartono)"
        r"(?: al (?:primo|secondo|terzo|quarto|quinto|[0-9]+) piano)?"
        r"(?: e non (?:riparte|ripartono))?"
        r"|interruzione totale(?: della (?:rete|corrente))?"
        r"|blackout totale|servizio completamente interrotto"
        r"|(?:riscaldamento|rete|internet) (?:è )?"
        r"(?:completamente|totalmente) (?:assente|bloccato|inutilizzabile|interrotto)"
        r"|(?:tutto l edificio|intero edificio|tutto il palazzo|intero palazzo) "
        r"(?:è )?senza (?:riscaldamento|corrente|internet|rete))"
    )
    safety_denial = (
        r"(?:non (?:ci sono|c è)|nessun[oa]?|senza|assenza di) "
        r"(?:persone (?:intrappolate|bloccate)|pericolo|rischio per le persone"
        r"|scintille(?: (?:né|e) cavi scoperti)?|incendio|fumo)"
    )
    return bool(clauses) and all(
        re.fullmatch(blockage + "|" + safety_denial, clause)
        for clause in clauses
    )


def _unambiguous_blockage_from_source(source_text: str) -> bool:
    """Assess only the report after removing bounded, non-priority metadata."""
    text = re.sub(
        r"\b(?:telefono|tel|cellulare|cell)\s*:?\s*"
        r"\+?\d[\d\s().-]{5,}\d",
        " ",
        source_text,
        flags=re.IGNORECASE,
    )
    # This deliberately requires an email cue and one bounded token: it does not
    # discard arbitrary prose merely because it contains punctuation.
    text = re.sub(
        r"\b(?:e-mail|email|mail)\b\s*(?:è\s*)?:?\s*"
        r"[A-Za-z0-9][A-Za-z0-9._@-]{0,254}(?=\s*(?:[,;!?]|\.(?=\s|$)|$))",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Address stripping can leave this grammatical lead-in as an empty clause.
    text = re.sub(r"\b(?:il\s+)?guasto\s+è\s+in\b", " ", text, flags=re.IGNORECASE)
    clauses = [clause for clause in _priority_clauses(text) if clause]
    return _unambiguous_blockage(clauses)


def reconcile_priority(source_text: str, provider_priority: Priority | None) -> Priority | None:
    """Reconcile a validated proposal using only the original report/transcript."""
    evidence = priority_fallback(source_text)
    if evidence == Priority.URGENTE:
        return Priority.URGENTE
    if evidence == Priority.ALTA:
        if provider_priority == Priority.URGENTE and _complete_heating_outage(
            _priority_clauses(source_text)
        ):
            return Priority.ALTA
        if provider_priority == Priority.URGENTE and not _unambiguous_blockage_from_source(source_text):
            return provider_priority
        return Priority.ALTA
    if provider_priority is None:
        return evidence
    return provider_priority
