"""Explanation generation: a plain baseline vs. a specialised 'DJ Vibe' style."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

from .llm import LLMError

logger = logging.getLogger("vibefinder.explain")

MAX_WORDS = 90
FEW_SHOT = """You are DJ Vibe. Rules: max 80 words, exactly 3 sentences,
cite the guide in square brackets, quote real numbers, only mention listed songs.

Example 1
Request: gym music. Guide: [activities#Workout] energy 0.80-0.98.
Picks: Gym Hero by Max Pulse (energy 0.93).
Answer: Lifting wants tempo and drive [activities#Workout]. "Gym Hero" by Max Pulse hits energy 0.93, right inside the 0.80-0.98 sweet spot. Start your first set with it.

Example 2
Request: quiet study music. Guide: [activities#Studying] energy 0.20-0.45.
Picks: Library Rain by Paper Lanterns (energy 0.40).
Answer: Studying works best with steady, low-energy sound [activities#Studying]. "Library Rain" by Paper Lanterns sits at energy 0.40, inside the 0.20-0.45 range. Press play and settle in.
"""

Scored = Tuple[dict, float, List[str]]


def baseline_explanation(scored: List[Scored]) -> str:
    """Plain, ungrounded explanation: just the scorer's reasons."""
    lines = []
    for song, score, reasons in scored[:3]:
        lines.append(f"{song['title']} by {song['artist']} (score {score:.2f}): "
                     + "; ".join(reasons) + ".")
    return " ".join(lines)


def specialised_explanation(scored: List[Scored], profile, docs, issues: List[str]) -> str:
    """Constrained DJ-Vibe style: 3 sentences, cited, numeric, grounded."""
    top = scored[0][0]
    primary = docs[0] if docs else None
    cite = f" [{primary.doc_id}]" if primary else ""
    if primary and primary.fields.get("tip"):
        opener = primary.fields["tip"].rstrip(".") + cite + "."
    elif primary:
        opener = f"{primary.title} guidance applies here{cite}."
    else:
        opener = "No guide matched, so this is based on your exact words."
    rng = primary.field_range("typical energy") if primary else None
    span = f", inside the {rng[0]:.2f}-{rng[1]:.2f} range" if (
        rng and rng[0] <= float(top["energy"]) <= rng[1]) else ""
    second = (f"\"{top['title']}\" by {top['artist']} has energy "
              f"{float(top['energy']):.2f}{span} and danceability "
              f"{float(top['danceability']):.2f}.")
    extra = ""
    if len(scored) > 1:
        extra = f" Keep \"{scored[1][0]['title']}\" queued next."
    caveat = ""
    if "energy_mismatch" in issues or "genre_miss" in issues:
        caveat = " Heads up: the closest tracks only partly match your energy request."
    return f"{opener} {second}{extra}{caveat}".strip()


def grounded(text: str, scored: List[Scored], doc_ids: List[str]) -> bool:
    """Check an explanation stays inside the listed songs and retrieved docs."""
    if len(text.split()) > MAX_WORDS + 40:
        return False
    titles = {str(s["title"]) for s, _, _ in scored}
    if not any(t in text for t in titles):
        return False
    for cited in re.findall(r"\[([^\]]+)\]", text):
        if cited not in doc_ids:
            return False
    return True


def llm_explanation(llm, scored: List[Scored], profile, docs) -> str | None:
    """Few-shot LLM explanation; None when it fails the grounding check."""
    picks = "; ".join(f"{s['title']} by {s['artist']} (energy {float(s['energy']):.2f})"
                      for s, _, _ in scored[:2])
    guide = "; ".join(f"[{d.doc_id}] energy {d.fields.get('typical energy', 'n/a')}"
                      for d in docs[:2]) or "none"
    prompt = (f"{FEW_SHOT}\nNow your turn\nRequest profile: {profile.describe()}\n"
              f"Guide: {guide}\nPicks: {picks}\nAnswer:")
    try:
        text = llm.complete(prompt).strip()
    except LLMError as err:
        logger.warning("LLM explanation failed: %s", err)
        return None
    return text if grounded(text, scored, [d.doc_id for d in docs]) else None


def metrics(text: str) -> Dict[str, int]:
    """Measurable properties used to compare baseline vs specialised output."""
    return {"words": len(text.split()),
            "citations": len(re.findall(r"\[[^\]]+\]", text)),
            "numbers": len(re.findall(r"\d+\.\d+", text))}