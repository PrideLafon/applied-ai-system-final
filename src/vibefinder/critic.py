"""Self-check step: critique the ranked results before answering."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

MAX_PER_ARTIST = 2
ENERGY_TOLERANCE = 0.35
WEAK_MATCH_RATIO = 0.55


def critique(scored: List[Tuple[dict, float, List[str]]], prefs: Dict[str, object],
             genre_source: str, k: int, max_score: float) -> List[str]:
    """Return a list of issue codes found in the top-k results."""
    issues: List[str] = []
    top = scored[:k]
    if len(top) < k:
        issues.append("too_few_results")
    if not top:
        return issues + ["no_results"]
    artists = Counter(str(s["artist"]) for s, _, _ in top)
    if any(n > MAX_PER_ARTIST for n in artists.values()):
        issues.append("artist_repeat")
    if abs(float(top[0][0]["energy"]) - float(prefs["energy"])) > ENERGY_TOLERANCE:
        issues.append("energy_mismatch")
    if prefs.get("genre") and genre_source == "user" and top[0][0]["genre"] != prefs["genre"]:
        issues.append("genre_miss")
    if max_score and top[0][1] / max_score < WEAK_MATCH_RATIO:
        issues.append("weak_match")
    return issues


def diversify(scored: List[Tuple[dict, float, List[str]]], k: int
              ) -> List[Tuple[dict, float, List[str]]]:
    """Re-rank so no artist appears more than MAX_PER_ARTIST times."""
    counts: Counter = Counter()
    picked, rest = [], []
    for item in scored:
        artist = str(item[0]["artist"])
        if counts[artist] < MAX_PER_ARTIST:
            counts[artist] += 1
            picked.append(item)
        else:
            rest.append(item)
    return (picked + rest)[:k]