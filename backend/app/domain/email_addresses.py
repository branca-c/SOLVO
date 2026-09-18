"""Conservative contact syntax and audio-only reconstruction; no providers or IO."""
import re


def valid_email(value: str) -> bool:
    if len(value) > 255 or value.count("@") != 1:
        return False
    local, domain = value.split("@")
    if not local or len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+", local):
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?", label)
        for label in labels
    ) and bool(re.fullmatch(r"[A-Za-z]{2,63}", labels[-1]))


EMAIL_CUE = re.compile(r"\b(?:e-mail|email|mail)\b\s*(?:(?:è|e'|is)\s*|:\s*)?", re.I)
# Read a single bounded contact expression, never the whole sentence. Spaces are
# allowed only beside spoken separators and a numeric suffix, not arbitrary prose.
EXPRESSION = re.compile(
    r"[A-Za-z0-9_]+(?:\s+\d+)*"
    r"(?:(?:[.@_\-]|\s+(?:chiocciola|at|punto|underscore)\s+|\s+(?=(?:chiocciola|at|punto|underscore))"
    r"|(?<=chiocciola)\s+|(?<=punto)\s+|(?<=underscore)\s+|(?<=at)\s+)"
    r"[A-Za-z0-9_]+(?:\s+\d+)*)*", re.I,
)

COMMON_EMAIL_DOMAINS = (
    "gmail.com", "outlook.com", "hotmail.com", "yahoo.com",
    "libero.it", "virgilio.it", "icloud.com",
)


def _distance_one(left: str, right: str) -> bool:
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    if len(left) > len(right):
        left, right = right, left
    return len(right) == len(left) + 1 and any(
        right[:i] + right[i + 1:] == left for i in range(len(right))
    )


def _canonical_domain(value: str) -> str | None:
    local, domain = value.split("@")
    if domain.lower() in COMMON_EMAIL_DOMAINS:
        return value
    matches = [item for item in COMMON_EMAIL_DOMAINS if _distance_one(domain.lower(), item)]
    if len(matches) > 1:
        return None
    return local + "@" + matches[0] if matches else value


def _reconstruct(expression: str) -> str | None:
    # Literal valid addresses are evidence, not spoken tokens to reinterpret.
    if valid_email(expression):
        return expression
    value = re.sub(
        r"\s*(chiocciola|punto|underscore)\s*",
        lambda m: {"chiocciola": "@", "punto": ".", "underscore": "_"}[m[1].lower()],
        expression, flags=re.I,
    )
    value = re.sub(r"\s+", "", value)
    if "@" in value:
        choices = [value] if valid_email(value) else []
    else:
        # 'at' can also occur in names. Try each position separately; accept only
        # a unique valid interpretation, never replace every 'at' indiscriminately.
        choices = [value[:m.start()] + "@" + value[m.end():]
                   for m in re.finditer("at", value, re.I)
                   if valid_email(value[:m.start()] + "@" + value[m.end():])]
        if not choices and "--" not in value:
            choices = [value[:i] + "@" + value[i + 1:]
                       for i, char in enumerate(value) if char == "-"
                       and valid_email(value[:i] + "@" + value[i + 1:])]
    if len(choices) != 1:
        return None
    result = _canonical_domain(choices[0])
    return result if result and valid_email(result) else None


def audio_email_candidate(transcript: str) -> str | None:
    candidates = []
    for cue in EMAIL_CUE.finditer(transcript):
        tail = transcript[cue.end():]
        match = EXPRESSION.match(tail[:256])
        if not match or match.end() > 255:
            return None
        # Reject a truncated expression rather than treating its prefix as email.
        remainder = tail[match.end():]
        if re.match(r"[\w@_\-]|\.(?:[\w.]|\s*\d)|\s+(?:chiocciola|at|punto|underscore)\b", remainder, re.I):
            return None
        value = _reconstruct(match[0])
        if value is None:
            return None
        candidates.append(value)
    return candidates[0] if candidates and len(set(candidates)) == 1 else None


def email_grounded(value: str, text: str) -> bool:
    # Preserve all email punctuation. A suffix of another address is not evidence.
    return bool(re.search(
        r"(?<![\w.!#$%&'*+/=?^_`{|}~@\-])" + re.escape(value)
        + r"(?![\w@_\-]|\.[\w])", text,
    ))
