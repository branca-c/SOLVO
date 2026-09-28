"""Source-grounded draft descriptions; no provider, HTTP or persistence access."""
from dataclasses import dataclass
import re
from collections.abc import Iterable, Sequence


MAX_SELECTED_SOURCE_SEGMENTS = 4
MAX_FAULT_QUOTES = 2
# Matches the existing public request and draft-description maximum.
MAX_RECONSTRUCTED_DESCRIPTION_LENGTH = 10_000
LONG_SEGMENT_THRESHOLD = 160
MIN_COMMA_CLAUSE_LENGTH = 24


@dataclass(frozen=True)
class SourceSegment:
    """An exact, server-calculated slice of the original report."""

    id: str
    start: int
    end: int
    text: str


_STRUCTURAL_BOUNDARY = re.compile(r"[!?;]+|(?:\r\n|\r|\n)+|(?<=\s)[•\-–—](?=\s)")
_ABBREVIATIONS = frozenset({
    "sig", "sig.ra", "sig.na", "dott", "dott.ssa", "prof", "prof.ssa",
    "ing", "arch", "avv", "geom", "n", "civ", "ecc",
})
_PHONE_IN_SEGMENT = re.compile(r"\+?\d[\d\s().-]{5,}\d")
_EMAIL_IN_SEGMENT = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_POSTAL_ADDRESS_ONLY = re.compile(
    r"\s*(?:(?:indirizzo|sede|luogo)\s*:\s*)?"
    r"(?:via|viale|corso|piazza|vicolo|largo)\s+[^.;!?\n]*?\d+[A-Za-z]?"
    r"(?:\s+(?:a|in)\s+(?-i:[A-ZÀ-Ý][\wà-ÿ'’-]*(?:\s+[A-ZÀ-Ý][\wà-ÿ'’-]*){0,2}))?"
    r"(?:,\s*(?-i:[A-ZÀ-Ý][\wà-ÿ'’-]*(?:\s+[A-ZÀ-Ý][\wà-ÿ'’-]*){0,2}))?"
    r"(?:\s*\([A-Za-z]{2}\))?\s*[.,;]?\s*\Z",
    re.IGNORECASE,
)


def _append_segment(
    source: str, segments: list[SourceSegment], start: int, end: int,
) -> None:
    """Append one non-empty source slice, excluding only boundary whitespace."""
    text = source[start:end]
    leading = len(text) - len(text.lstrip())
    trailing = len(text) - len(text.rstrip())
    segment_start = start + leading
    segment_end = end - trailing
    if segment_start < segment_end:
        segments.append(SourceSegment(
            id=f"S{len(segments) + 1}",
            start=segment_start,
            end=segment_end,
            text=source[segment_start:segment_end],
        ))


def _is_abbreviation_period(source: str, period: int) -> bool:
    """Keep a deliberately small set of common operational abbreviations intact."""
    prefix = source[:period]
    normalized = prefix.casefold()
    for abbreviation in _ABBREVIATIONS:
        if not normalized.endswith(abbreviation):
            continue
        start = len(prefix) - len(abbreviation)
        if start == 0 or not prefix[start - 1].isalnum():
            return True
    return False


def _is_sentence_period(source: str, period: int) -> bool:
    if _is_abbreviation_period(source, period):
        return False
    following = source[period + 1:]
    return not following or bool(re.match(r"\s+[A-ZÀ-Ý]", following))


def _structural_ranges(source: str) -> Iterable[tuple[int, int]]:
    """Yield coarse ranges delimited by clear punctuation, lines and list markers."""
    segment_start = 0
    scan_start = 0
    while scan_start < len(source):
        structural = _STRUCTURAL_BOUNDARY.search(source, scan_start)
        period = source.find(".", scan_start)
        if period >= 0 and (structural is None or period < structural.start()):
            if _is_sentence_period(source, period):
                yield segment_start, period + 1
                segment_start = period + 1
            scan_start = period + 1
            continue
        if structural is None:
            break
        boundary_text = structural.group()
        end = structural.end() if boundary_text[0] in "!?;" else structural.start()
        yield segment_start, end
        segment_start = structural.end()
        scan_start = structural.end()
    yield segment_start, len(source)


def _comma_boundaries(source: str, start: int, end: int) -> list[int]:
    """Split only long comma chains into bounded structural clauses."""
    if end - start < LONG_SEGMENT_THRESHOLD:
        return []
    email_ranges = [
        (start + match.start(), start + match.end())
        for match in _EMAIL_IN_SEGMENT.finditer(source[start:end])
    ]
    boundaries: list[int] = []
    clause_start = start
    for position in range(start, end):
        if source[position] != ",":
            continue
        if (position > start and position + 1 < end
                and source[position - 1].isdigit() and source[position + 1].isdigit()):
            continue
        if any(email_start <= position < email_end for email_start, email_end in email_ranges):
            continue
        before = source[clause_start:position + 1].strip()
        after = source[position + 1:end].strip()
        if len(before) < MIN_COMMA_CLAUSE_LENGTH or len(after) < MIN_COMMA_CLAUSE_LENGTH:
            continue
        boundaries.append(position + 1)
        clause_start = position + 1
    return boundaries


def segment_source(source_text: str) -> list[SourceSegment]:
    """Split source at structural boundaries and only long comma-chained clauses."""
    segments: list[SourceSegment] = []
    for start, end in _structural_ranges(source_text):
        clause_start = start
        for comma_end in _comma_boundaries(source_text, start, end):
            _append_segment(source_text, segments, clause_start, comma_end)
            clause_start = comma_end
        _append_segment(source_text, segments, clause_start, end)
    return segments


def segment_is_safe_for_description(
    segment: SourceSegment,
    *,
    requester_first_name: str | None = None,
    requester_last_name: str | None = None,
) -> bool:
    """Reject clear structured/contact material without rewriting selected text."""
    text = segment.text
    if _PHONE_IN_SEGMENT.search(text) or _EMAIL_IN_SEGMENT.search(text):
        return False
    if requester_first_name and requester_last_name:
        full_name = re.compile(
            rf"(?<!\w){re.escape(requester_first_name)}\s+{re.escape(requester_last_name)}(?!\w)",
            re.IGNORECASE,
        )
        if full_name.search(text):
            return False
    return not _POSTAL_ADDRESS_ONLY.fullmatch(text)


def reconstruct_selected_segments(
    segments: Sequence[SourceSegment],
    selected_ids: Iterable[str],
    *,
    requester_first_name: str | None = None,
    requester_last_name: str | None = None,
) -> str:
    """Rebuild a description exclusively from known, safe server source slices."""
    selected = {segment_id for segment_id in selected_ids if isinstance(segment_id, str)}
    known = {segment.id: segment for segment in segments}
    accepted = [
        segment for segment in sorted(known.values(), key=lambda item: item.start)
        if segment.id in selected and segment_is_safe_for_description(
            segment,
            requester_first_name=requester_first_name,
            requester_last_name=requester_last_name,
        )
    ]

    parts: list[str] = []
    length = 0
    for segment in accepted:
        if len(parts) == MAX_SELECTED_SOURCE_SEGMENTS:
            break
        addition = len(segment.text) + (1 if parts else 0)
        if length + addition > MAX_RECONSTRUCTED_DESCRIPTION_LENGTH:
            continue
        parts.append(segment.text)
        length += addition
    return " ".join(parts)


def _quote_is_safe_for_description(
    quote: str,
    *,
    requester_first_name: str | None = None,
    requester_last_name: str | None = None,
    fault_address: str | None = None,
) -> bool:
    if _PHONE_IN_SEGMENT.search(quote) or _EMAIL_IN_SEGMENT.search(quote):
        return False
    if requester_first_name and requester_last_name:
        full_name = re.compile(
            rf"(?<!\w){re.escape(requester_first_name)}\s+{re.escape(requester_last_name)}(?!\w)",
            re.IGNORECASE,
        )
        if full_name.search(quote):
            return False
    if _POSTAL_ADDRESS_ONLY.fullmatch(quote):
        return False
    if fault_address:
        quote_tokens = " ".join(re.findall(r"\w+", quote.casefold()))
        address_tokens = " ".join(re.findall(r"\w+", fault_address.casefold()))
        if quote_tokens and quote_tokens == address_tokens:
            return False
    return True


def reconstruct_fault_quotes(
    segments: Sequence[SourceSegment],
    quotes: Iterable[tuple[str, str]],
    *,
    requester_first_name: str | None = None,
    requester_last_name: str | None = None,
    fault_address: str | None = None,
) -> str:
    """Rebuild a description only from exact, safe substrings of issued segments."""
    known = {segment.id: segment for segment in segments}
    accepted: list[tuple[int, int, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in quotes:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        segment_id, quote = item
        if not isinstance(segment_id, str) or not isinstance(quote, str) or not quote:
            continue
        duplicate_key = (segment_id, quote)
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        segment = known.get(segment_id)
        if segment is None:
            continue
        start = segment.text.find(quote)
        if start < 0 or not _quote_is_safe_for_description(
            quote,
            requester_first_name=requester_first_name,
            requester_last_name=requester_last_name,
            fault_address=fault_address,
        ):
            continue
        end = start + len(quote)
        accepted.append((segment.start + start, segment.start + end, segment.text[start:end]))

    parts: list[str] = []
    length = 0
    previous_end = -1
    for start, end, quote in sorted(accepted):
        if len(parts) == MAX_FAULT_QUOTES:
            break
        if start < previous_end:
            continue
        addition = len(quote) + (1 if parts else 0)
        if length + addition > MAX_RECONSTRUCTED_DESCRIPTION_LENGTH:
            continue
        parts.append(quote)
        length += addition
        previous_end = end
    return " ".join(parts)


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
