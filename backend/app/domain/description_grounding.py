"""Source-grounded draft descriptions; no provider, HTTP or persistence access."""
import re


# Function words may be introduced by harmless grammatical cleanup. Content words
# must remain in the source rather than being inferred or replaced with synonyms.
HARMLESS_WORDS = {
    "a", "ad", "al", "alla", "alle", "allo", "ai", "agli", "con", "che", "ci",
    "da", "dal", "dalla", "dalle", "dallo", "dei", "del", "della", "delle", "di",
    "e", "ed", "gli", "i", "il", "in", "la", "le", "lo", "nel", "nella", "nelle",
    "nello", "non", "o", "per", "piu", "più", "sul", "sulla", "sulle", "sullo",
    "tra", "un", "una", "uno", "è", "sono", "siamo",
}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[\wà-ÿ]+", text.casefold()))


def description_is_grounded(source_text: str, description: str) -> bool:
    """Allow only source content words, with a small function-word allowance."""
    source_words = _words(source_text)
    return all(word in source_words or word in HARMLESS_WORDS for word in _words(description))


def description_contains_separate_details(description: str) -> bool:
    """Descriptions must not repeat contact or street-address data."""
    return bool(
        re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", description)
        or re.search(r"\+?\d[\d\s().-]{5,}\d", description)
        or re.search(
            r"\b(?:via|viale|corso|piazza|vicolo|largo)\s+[^.;!?\n]*?\d+[A-Za-z]?\b",
            description,
            re.IGNORECASE,
        )
    )


def sanitize_description(text: str) -> str:
    """Remove bounded non-fault material from a selected description."""
    # Structured fields are removed as a whole so their labels cannot become
    # misleading description fragments after the value has been stripped.
    text = re.sub(
        r"(?:^|(?<=[.!?;]))\s*(?:buongiorno|ciao)\s*,?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:il\s+mio\s+(?:numero\s+di\s+)?telefono|telefono|tel|cellulare|cell)"
        r"\s*(?::|è)?\s*"
        r"\+?\d[\d\s().-]{5,}\d\s*[;,]?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:la\s+mia\s+)?(?:e-mail|email|mail)\s*(?::|è)?\s*"
        r"(?=[A-Za-z0-9._@-]*[.@_-])[A-Za-z0-9](?:[A-Za-z0-9._@-]{0,253}[A-Za-z0-9])?"
        r"\s*[;,]?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:indirizzo|address)\s*:?\s*[^;.!?\n]*(?:;\s*)?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", " ", text)
    text = re.sub(
        r"\b(?:telefono|tel|cellulare|cell)\s*:?\s*\+?\d[\d\s().-]{5,}\d",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:potete\s+)?chiamarmi\s+al\s*\+?\d[\d\s().-]{5,}\d\s*[;,]?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:potete\s+)?contattarmi\s+al\s+(?:cel(?:lulare)?|tel(?:efono)?)\.?\s*"
        r"\+?\d[\d\s().-]{5,}\d(?:\s+oppure\s+via\s+(?:e-?mail|mail)"
        r"(?:\s+a(?:\s+[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})?)?)?\s*[;,]?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:per il sopralluogo\s+)?(?:contattatemi|(?:potete\s+)?contattarmi)\b[^.?!]*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:^|(?<=[.!?;]))\s*(?:mi chiamo|sono)\s+"
        r"[A-ZÀ-Ý][a-zà-ÿ'’-]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ'’-]+){0,2}"
        r"(?:\s+e\s+vorrei\s+segnalare\b|"
        r"(?=\s*(?:[,.;]|\b(?:abito|risiedo|telefono|email|e-mail)\b)))",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:abito|risiedo)\s+in\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?:\b(?:nello|nella)\s+stabile\s+di\s+)?"
        r"\b(?:via|viale|corso|piazza|vicolo|largo)\s+[^.;!?\n]*?\d+[A-Za-z]?"
        r"(?:\s+(?:a|in)\s+(?-i:[A-ZÀ-Ý][\wà-ÿ'’-]*(?:\s+[A-ZÀ-Ý][\wà-ÿ'’-]*){0,2}))?"
        r"(?:,\s*(?-i:[A-ZÀ-Ý][\wà-ÿ'’-]*(?:\s+[A-ZÀ-Ý][\wà-ÿ'’-]*){0,2}))?"
        r"(?:\s*\([A-Za-z]{2}\))?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:nello|nella)\s+stabile\s+di\s*(?=[,;:.!?]|$)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(?:in|a|presso)\s*(?=[,;:.!?]|$)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:il\s+)?guasto\s+è\s+in\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:il\s+)?guasto\s+è\s*(?=[,;:.!?]|$)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:vorrei\s+)?segnalare(?:\s+che)?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bun\s+guasto\s+urgentissimo\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bchiedo\s+(?:un\s+)?intervento(?:\s+di\s+manutenzione)?(?:\s+sull[’']impianto)?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bil prima possibile\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bintervenite\s+al\s+più\s+presto\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvi\s+prego\s+di\s+intervenire\s+al\s+più\s+presto\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:grazie|saluti|cordiali saluti)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[,;]\s*(?=[.!?])", "", text)
    text = re.sub(r"\s*([,;:.!?])\s*", r"\1 ", text)
    text = re.sub(r"([,;:.!?])(?:\s*[,;:.!?])+", r"\1", text)
    text = re.sub(r"^[,;:.!?]+\s*", "", text).strip(" ,;:!?")
    return text[:1].upper() + text[1:] if text else ""


def source_grounded_description(source_text: str) -> str:
    """Return an extractive, privacy-cleaned description from the original report."""
    return sanitize_description(source_text)
