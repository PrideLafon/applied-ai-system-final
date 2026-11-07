"""Input and profile guardrails."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

MIN_QUERY_CHARS = 3
MAX_QUERY_CHARS = 300

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard .{0,30}(rules|instructions|prompt)",
    r"(reveal|show|print|repeat) .{0,30}(system prompt|instructions|api[_ ]?key)",
    r"you are now ",
    r"act as (an? )?(?!dj)",
    r"\bapi[_ ]?key\b",
    r"<\s*script",
]
_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


@dataclass
class ValidationResult:
    """Outcome of validating a user query."""

    ok: bool
    cleaned: str = ""
    reason: str = ""


def validate_query(query: object) -> ValidationResult:
    """Validate and clean a raw user query.

    Rejects non-strings, empty/too-short/too-long text, text with no
    letters, and likely prompt-injection attempts.
    """
    if not isinstance(query, str):
        return ValidationResult(False, reason="Query must be text.")
    cleaned = re.sub(r"\s+", " ", _CONTROL.sub(" ", query)).strip()
    if len(cleaned) < MIN_QUERY_CHARS:
        return ValidationResult(False, reason="Query is empty or too short.")
    if len(cleaned) > MAX_QUERY_CHARS:
        return ValidationResult(
            False, reason=f"Query is too long (max {MAX_QUERY_CHARS} chars).")
    if not re.search(r"[A-Za-z]{2,}", cleaned):
        return ValidationResult(False, reason="Query has no readable words.")
    for pattern in _INJECTION:
        if pattern.search(cleaned):
            return ValidationResult(
                False, reason="Query looks like a prompt-injection attempt.")
    return ValidationResult(True, cleaned=cleaned)


def _clamp(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return max(0.0, min(1.0, number))


def sanitize_profile_dict(raw: Dict[str, Any], genres: Set[str],
                          moods: Set[str]) -> Dict[str, Any]:
    """Validate a profile dict (e.g. LLM JSON output) against the catalog.

    Unknown genres or moods become None, numbers are clamped to 0-1, and
    unexpected keys are dropped.
    """
    clean: Dict[str, Any] = {"genre": None, "mood": None,
                             "energy": None, "danceability": None}
    genre = str(raw.get("genre") or "").strip().lower()
    mood = str(raw.get("mood") or "").strip().lower()
    clean["genre"] = genre if genre in genres else None
    clean["mood"] = mood if mood in moods else None
    clean["energy"] = _clamp(raw.get("energy"))
    clean["danceability"] = _clamp(raw.get("danceability"))
    return clean


@dataclass
class GuardrailReport:
    """Collected guardrail events for the trace."""

    events: List[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.events.append(text)