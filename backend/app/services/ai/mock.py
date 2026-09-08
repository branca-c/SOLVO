import re

# Category names are proposals, never database IDs.
CATEGORY_PATTERNS = {
    "Ascensore": r"\bascensor[ei]\b",
    "Idraulico": r"\b(?:perdit[ae]|acqua|tub[oi]|rubinett[oi]|gocciola)\b",
    "Rete": r"\b(?:rete|internet|connessione|wi-?fi)\b",
    "Climatizzazione": r"\b(?:condizionator[ei]|climatizzator[ei])\b",
    "Riscaldamento": r"\b(?:riscaldamento|calorifer[oi]|termosifon[ei])\b",
    "Vetri": r"\b(?:vetr[oi]|finestra rotta)\b",
    "Elettrico": r"\b(?:corrente|elettric[oa]|blackout|presa|cortocircuito)\b",
}


def _labelled(text: str, label: str) -> str | None:
    match = re.search(rf"\b(?:{label})\s*:\s*([^;\n]+)", text, re.IGNORECASE)
    if not match:
        return None
    # Explicit key/value fields end at a delimiter or the next known label.
    value = re.split(
        r",\s*(?=(?:nome|cognome|telefono|tel|cellulare|email|e-mail|indirizzo|categoria)\s*:)",
        match.group(1), maxsplit=1, flags=re.IGNORECASE,
    )[0].strip().rstrip(".")
    return value or None


def _positive(pattern: str, text: str) -> bool:
    for match in re.finditer(pattern, text, re.IGNORECASE):
        prefix = text[max(0, match.start() - 40):match.start()]
        if not re.search(
            r"(?:\bnon(?:\s+(?:è|sono|c['’]è|ci sono))?|\bnessun[oa]?|\bsenza|\bassenza di)\s*$",
            prefix, re.IGNORECASE,
        ):
            return True
    return False


def _priority(text: str) -> str | None:
    if _positive(
        r"\b(?:urgente|pericolo|rischio immediato|rischi(?:o)? per (?:le )?persone|"
        r"persone (?:intrappolate|bloccate|dentro)|incendio|fuga di gas)\b", text,
    ):
        return "URGENTE"
    if _positive(
        r"\b(?:blackout|bloccato|bloccata|blocco totale|interruzione totale|"
        r"assenza totale|senza corrente|fuori servizio)\b", text,
    ):
        return "ALTA"
    if re.search(r"\b(?:non urgente|programmabile|manutenzione programmata|pianificat[oa])\b", text, re.I):
        return "PROGRAMMABILE"
    if _positive(r"\b(?:lieve|piccolo inconveniente|piccolo fastidio|minore|gocciola)\b", text):
        return "BASSA"
    if re.search(r"\b(?:guasto|rott[oaie]|perdit[ae]|non funziona|malfunzionamento|problema)\b", text, re.I):
        return "MEDIA"
    return None


class MockAIProvider:
    """Conservative deterministic heuristics, not a language model."""

    def extract(self, text: str) -> object:
        first_name = _labelled(text, "nome")
        last_name = _labelled(text, "cognome")
        # Free-form names require an explicit introduction and two capitalized tokens.
        name = re.search(
            r"(?i:mi chiamo)\s+([A-ZÀ-Ý][a-zà-ÿ'’\-]+)\s+([A-ZÀ-Ý][a-zà-ÿ'’\-]+)"
            r"(?=\s*[,;.!\n]|\s*$)", text,
        )
        if name:
            first_name = first_name or name.group(1)
            last_name = last_name or name.group(2)
        phone = re.search(
            r"\b(?:telefono|tel|cellulare|cell)\s*:?\s*(\+?\d[\d ()\-]{4,30}\d)(?!\d)",
            text, re.I,
        )
        email = re.search(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
        address = _labelled(text, "indirizzo")
        if address is None:
            match = re.search(
                r"\b(?:via|viale|piazza|corso|vicolo)\s+[^;\n.!?]{1,100}?\s+\d+[A-Za-z]?\b",
                text, re.I,
            )
            address = match.group(0) if match else None
        proposed_category = _labelled(text, "categoria")
        categories = [name for name, pattern in CATEGORY_PATTERNS.items() if re.search(pattern, text, re.I)]
        warnings = []
        if not proposed_category:
            if len(categories) == 1:
                proposed_category = categories[0]
            elif len(categories) > 1:
                warnings.append("Il testo riguarda più categorie: scegli quella corretta.")
        return {
            "user_first_name": first_name,
            "user_last_name": last_name,
            "user_phone": phone.group(1).strip() if phone else None,
            "user_email": email.group(0) if email else None,
            "fault_address": address,
            "category_name": proposed_category,
            "priority": _priority(text),
            "description": text,
            "warnings": warnings,
        }
