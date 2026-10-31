"""Conservative extraction of owner-authored facts suitable for local retention."""
import re

_CANDIDATE = re.compile(
    r"^\s*(?:remember(?: that)?|tandaan(?: mo)?(?: na)?|i (?:prefer|like)|my preference is|"
    r"please remember|gusto ko(?:ng)?|mas gusto ko)\b[\s,:-]*(.+)$", re.IGNORECASE | re.DOTALL)
_SECRET = re.compile(
    r"\b(?:password|passphrase|api[ _-]?key|access[ _-]?token|secret|private[ _-]?key|bearer)\b",
    re.IGNORECASE)


def retention_candidate(message: str) -> str | None:
    """Return exact owner text only for an explicit fact/preference, never likely secrets."""
    text=" ".join(message.strip().split())
    if not 8 <= len(text) <= 1000 or _SECRET.search(text):return None
    match=_CANDIDATE.match(text)
    if not match or len(match.group(1).strip()) < 3 or text.endswith('?'):return None
    return text
