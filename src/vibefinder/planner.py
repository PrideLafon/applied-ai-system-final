"""Planning step: turn free text into a structured taste profile.

Explicit user words always win. Missing fields are filled from retrieved
knowledge (RAG), which is what makes retrieval change system behaviour.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .guardrails import sanitize_profile_dict
from .llm import LLMError
from .retriever import Doc

logger = logging.getLogger("vibefinder.planner")

ENERGY_WORDS = {
    "high energy": 0.88, "high-energy": 0.88, "energetic": 0.85, "pumped": 0.9,
    "intense": 0.88, "hype": 0.9, "upbeat": 0.78, "loud": 0.9, "fast": 0.8,
    "low energy": 0.25, "low-energy": 0.25, "mellow": 0.3, "calm": 0.25,
    "quiet": 0.2, "soft": 0.2, "slow": 0.25, "gentle": 0.2, "sleepy": 0.15,
}
DANCE_WORDS = {"danceable": 0.85, "dance": 0.85, "dancing": 0.85, "groove": 0.72,
               "groovy": 0.72, "party": 0.88}
MOOD_WORDS = {
    "sad": "moody", "rainy": "moody", "melancholy": "moody", "melancholic": "moody",
    "dark": "moody", "moody": "moody", "happy": "happy", "joyful": "happy",
    "cheerful": "happy", "chill": "chill", "relax": "relaxed",
    "relaxed": "relaxed", "relaxing": "relaxed", "focus": "focused",
    "focused": "focused", "concentrate": "focused", "angry": "intense",
    "aggressive": "intense", "intense": "intense",
}
GENRE_ALIASES = {"lo-fi": "lofi", "rap": "hip hop", "hip-hop": "hip hop",
                 "indie": "indie pop", "orchestral": "classical"}


@dataclass
class Profile:
    """A structured taste profile plus where each field came from."""

    genre: Optional[str] = None
    mood: Optional[str] = None
    energy: Optional[float] = None
    danceability: Optional[float] = None
    activity: Optional[str] = None
    seed_song: Optional[str] = None
    sources: Dict[str, str] = field(default_factory=dict)

    def known_fields(self) -> int:
        """How many of the four scoring fields are known (not defaults)."""
        return sum(v is not None for v in
                   (self.genre, self.mood, self.energy, self.danceability))

    def to_prefs(self) -> Dict[str, object]:
        """Scoring preferences; unknown numbers fall back to neutral 0.5."""
        return {"genre": self.genre, "mood": self.mood,
                "energy": 0.5 if self.energy is None else self.energy,
                "danceability": 0.5 if self.danceability is None else self.danceability}

    def describe(self) -> dict:
        """Plain dict for logs and traces."""
        return {"genre": self.genre, "mood": self.mood, "energy": self.energy,
                "danceability": self.danceability, "activity": self.activity,
                "seed_song": self.seed_song, "sources": dict(self.sources)}


def _has(query: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", query) is not None


def rule_based_parse(query: str, genres: Set[str], moods: Set[str]) -> Profile:
    """Offline parser that finds explicit genre, mood, energy and dance words."""
    q = query.lower()
    profile = Profile()
    names = sorted(genres | set(GENRE_ALIASES), key=len, reverse=True)
    for name in names:
        if _has(q, name):
            genre = GENRE_ALIASES.get(name, name)
            if genre in genres:
                profile.genre, profile.sources["genre"] = genre, "user"
                break
    for word, mood in MOOD_WORDS.items():
        if mood in moods and _has(q, word):
            profile.mood, profile.sources["mood"] = mood, "user"
            break
    for word in sorted(ENERGY_WORDS, key=len, reverse=True):
        if _has(q, word):
            profile.energy, profile.sources["energy"] = ENERGY_WORDS[word], "user"
            break
    for word in sorted(DANCE_WORDS, key=len, reverse=True):
        if _has(q, word):
            profile.danceability = DANCE_WORDS[word]
            profile.sources["danceability"] = "user"
            break
    return profile


def find_seed_song(query: str, songs: List[dict]) -> Optional[dict]:
    """Songs source: if the user names a song or artist, use it as a seed."""
    q = query.lower()
    for song in songs:
        if len(str(song["title"])) >= 4 and str(song["title"]).lower() in q:
            return song
    for song in songs:
        if str(song["artist"]).lower() in q:
            return song
    return None


def apply_seed(profile: Profile, song: dict) -> List[str]:
    """Fill missing fields from a named seed song ('more like X')."""
    notes = []
    for name in ("genre", "mood", "energy", "danceability"):
        if getattr(profile, name) is None:
            setattr(profile, name, song[name])
            profile.sources[name] = f"songs#{song.get('id')}"
    profile.seed_song = str(song["title"])
    notes.append(f"seeded missing fields from song '{song['title']}'")
    return notes


def enrich_from_docs(profile: Profile, docs: List[Doc], genres: Set[str],
                     moods: Set[str]) -> List[str]:
    """RAG step: fill missing profile fields from retrieved guidance docs."""
    notes: List[str] = []
    for doc in docs:
        if doc.kind == "activity" and profile.activity is None:
            profile.activity = doc.title
        if profile.energy is None and (r := doc.field_range("typical energy")):
            profile.energy = round(sum(r) / 2, 3)
            profile.sources["energy"] = doc.doc_id
            notes.append(f"energy={profile.energy} from {doc.doc_id}")
        if profile.danceability is None and (r := doc.field_range("typical danceability")):
            profile.danceability = round(sum(r) / 2, 3)
            profile.sources["danceability"] = doc.doc_id
            notes.append(f"danceability={profile.danceability} from {doc.doc_id}")
        if profile.genre is None:
            for g in doc.field_list("matching genres"):
                if g in genres:
                    profile.genre, profile.sources["genre"] = g, doc.doc_id
                    notes.append(f"genre={g} from {doc.doc_id}")
                    break
        if profile.mood is None:
            for m in doc.field_list("matching moods"):
                if m in moods:
                    profile.mood, profile.sources["mood"] = m, doc.doc_id
                    notes.append(f"mood={m} from {doc.doc_id}")
                    break
    return notes


def llm_parse(llm, query: str, docs: List[Doc], genres: Set[str],
              moods: Set[str]) -> Optional[Profile]:
    """Ask the LLM for a JSON profile grounded in retrieved context.

    Returns None on any failure so the caller can use the offline parser.
    """
    context = "\n".join(f"[{d.doc_id}] {d.text}" for d in docs) or "(none)"
    prompt = (
        "You convert a music request into a JSON taste profile.\n"
        f"Allowed genres: {sorted(genres)}\nAllowed moods: {sorted(moods)}\n"
        "Use ONLY these keys: genre, mood, energy (0-1), danceability (0-1).\n"
        "Use null when unsure. Use the context for typical numeric ranges.\n"
        f"Context:\n{context}\n\nRequest: {query}\n"
        "Reply with JSON only, no prose.")
    try:
        text = llm.complete(prompt)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("no JSON object in reply")
        data = sanitize_profile_dict(json.loads(match.group(0)), genres, moods)
    except (LLMError, ValueError, json.JSONDecodeError) as err:
        logger.warning("LLM planner failed (%s); using offline parser", err)
        return None
    profile = Profile(**data)
    profile.sources = {k: "llm" for k, v in data.items() if v is not None}
    return profile