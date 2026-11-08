"""Scoring bridge to the original Music Recommender (Project 3).

`builtin` is a simplified four-feature scorer modeled on the Project 3 idea:
    genre 2.0 (exact) + mood 1.0 (exact)
    + energy 1.5 x closeness + danceability 1.0 x closeness
It leaves out Project 3's extra features (ranking modes, diversity penalty,
language, mood tags, instrumentalness). `project` tries to call the real
`recommend_songs` from src/recommender.py and falls back to `builtin` if the
catalog lacks the columns that function needs.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("vibefinder.scoring")

W_GENRE, W_MOOD, W_ENERGY, W_DANCE = 2.0, 1.0, 1.5, 1.0
DEFAULT_SCORER = "builtin"  # change to "project" once your function checks out

Scored = Tuple[dict, float, List[str]]


def max_possible(prefs: Dict[str, object]) -> float:
    """Highest score a song can reach for these preferences."""
    total = W_ENERGY + W_DANCE
    total += W_GENRE if prefs.get("genre") else 0.0
    total += W_MOOD if prefs.get("mood") else 0.0
    return total


def builtin_score(prefs: Dict[str, object], song: dict) -> Tuple[float, List[str]]:
    """Score one song with the Project 3 recipe and explain why."""
    score, reasons = 0.0, []
    if prefs.get("genre"):
        if song["genre"] == prefs["genre"]:
            score += W_GENRE
            reasons.append(f"genre match ({song['genre']})")
    if prefs.get("mood"):
        if song["mood"] == prefs["mood"]:
            score += W_MOOD
            reasons.append(f"mood match ({song['mood']})")
    e_close = 1.0 - abs(float(song["energy"]) - float(prefs["energy"]))
    d_close = 1.0 - abs(float(song["danceability"]) - float(prefs["danceability"]))
    score += W_ENERGY * e_close + W_DANCE * d_close
    reasons.append(f"energy {song['energy']:.2f} vs target {prefs['energy']:.2f}")
    reasons.append(f"danceability {song['danceability']:.2f} vs target "
                   f"{prefs['danceability']:.2f}")
    return round(score, 3), reasons


def _builtin(prefs: Dict[str, object], songs: List[dict], k: int) -> List[Scored]:
    ranked = [(s, *builtin_score(prefs, s)) for s in songs]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:k]


def _project(prefs: Dict[str, object], songs: List[dict], k: int) -> Optional[List[Scored]]:
    """Call the student's Project 3 recommend_songs, normalising its output."""
    try:
        from src.recommender import recommend_songs  # type: ignore
    except Exception as err:
        logger.warning("Project 3 recommender not importable: %s", err)
        return None
    aliases = dict(prefs)
    aliases.update(favorite_genre=prefs.get("genre"), favorite_mood=prefs.get("mood"),
                   target_energy=prefs["energy"], target_danceability=prefs["danceability"])
    try:
        raw = recommend_songs(aliases, songs, k)
        out: List[Scored] = []
        for item in raw:
            song, score = item[0], float(item[1])
            why = item[2] if len(item) > 2 else ""
            reasons = list(why) if isinstance(why, (list, tuple)) else [str(why)]
            if not isinstance(song, dict) or "title" not in song:
                raise ValueError("unexpected song shape")
            out.append((song, score, reasons))
        return out
    except Exception as err:
        logger.warning("Project 3 recommender failed (%s); using builtin", err)
        return None


def score_catalog(prefs: Dict[str, object], songs: List[dict], k: int = 5,
                  mode: Optional[str] = None) -> Tuple[List[Scored], str]:
    """Rank songs; returns (results, scorer_name_used)."""
    mode = (mode or os.getenv("VIBEFINDER_SCORER") or DEFAULT_SCORER).lower()
    if mode == "project":
        result = _project(prefs, songs, k)
        if result is not None:
            return result, "project"
    return _builtin(prefs, songs, k), "builtin"