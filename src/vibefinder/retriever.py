"""Multi-source retrieval: a markdown knowledge base plus the song catalog.

Uses a small, dependency-free BM25 ranker so the project runs anywhere.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("vibefinder.retriever")

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with", "i",
    "me", "my", "some", "something", "need", "want", "like", "music", "songs",
    "song", "play", "give", "that", "is", "it", "its", "at", "be", "good",
    "while", "when", "need", "really", "very", "just", "please", "tracks",
    # field labels that appear in every guide would otherwise match everything
    "energy", "high", "low", "typical", "danceability", "keywords", "keyword",
    "tip", "matching", "genres", "moods",
}
_RANGE = re.compile(r"(\d*\.?\d+)\s*-\s*(\d*\.?\d+)")


def stem(word: str) -> str:
    """Very light stemmer applied twice (studying -> study -> stud, dance -> danc)."""
    for _ in range(2):
        for suffix in ("ing", "ies", "ed", "es", "y", "s", "e"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                break
    return word


def tokenize(text: str) -> List[str]:
    """Lowercase, split, drop stopwords, and stem."""
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


@dataclass
class Doc:
    """One retrievable chunk."""

    doc_id: str
    source: str  # "knowledge" or "songs"
    kind: str  # activity | genre | mood | song
    title: str
    text: str
    fields: Dict[str, str] = field(default_factory=dict)

    def field_range(self, name: str) -> Optional[Tuple[float, float]]:
        """Parse a 'low-high' numeric field such as 'Typical energy'."""
        match = _RANGE.search(self.fields.get(name, ""))
        return (float(match.group(1)), float(match.group(2))) if match else None

    def field_list(self, name: str) -> List[str]:
        """Parse a comma-separated field into a lowercase list."""
        raw = self.fields.get(name, "")
        return [p.strip().lower() for p in raw.split(",") if p.strip()]


def load_knowledge(directory: str | Path) -> List[Doc]:
    """Split every markdown file in `directory` into one Doc per '## ' section."""
    docs: List[Doc] = []
    kind_by_file = {"activities": "activity", "genres": "genre", "moods": "mood"}
    for path in sorted(Path(directory).glob("*.md")):
        kind = kind_by_file.get(path.stem, path.stem)
        title, lines = None, []

        def flush() -> None:
            if title is None:
                return
            fields = {}
            for line in lines:
                m = re.match(r"-\s*([^:]+):\s*(.+)", line)
                if m:
                    fields[m.group(1).strip().lower()] = m.group(2).strip()
            docs.append(Doc(f"{path.stem}#{title}", "knowledge", kind, title,
                            f"{title}. " + " ".join(lines), fields))

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                flush()
                title, lines = line[3:].strip(), []
            elif title is not None and line.strip():
                lines.append(line.strip())
        flush()
    logger.info("Loaded %d knowledge sections", len(docs))
    return docs


def songs_to_docs(songs: List[dict]) -> List[Doc]:
    """Turn catalog rows into retrievable Docs (second retrieval source)."""
    return [Doc(f"songs#{s.get('id', i)}", "songs", "song", str(s["title"]),
                f"{s['title']} {s['artist']} {s['genre']} {s['mood']}",
                {"artist": str(s["artist"])}) for i, s in enumerate(songs)]


class Retriever:
    """BM25 retriever over a list of Docs."""

    def __init__(self, docs: List[Doc], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1, self.b = k1, b
        self._tokens = [Counter(tokenize(d.text)) for d in docs]
        self._lengths = [sum(c.values()) for c in self._tokens]
        self._avg = (sum(self._lengths) / len(docs)) if docs else 0.0
        self._df: Counter = Counter()
        for counts in self._tokens:
            self._df.update(counts.keys())

    def search(self, query: str, k: int = 3, source: Optional[str] = None,
               min_score: float = 1.0) -> List[Tuple[Doc, float]]:
        """Return up to k (Doc, score) pairs scoring at least `min_score`."""
        q = tokenize(query)
        if not q or not self.docs:
            return []
        n = len(self.docs)
        scored: List[Tuple[Doc, float]] = []
        for doc, counts, length in zip(self.docs, self._tokens, self._lengths):
            if source and doc.source != source:
                continue
            score = 0.0
            for term in set(q):
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * length / (self._avg or 1))
                score += idf * tf * (self.k1 + 1) / denom
            if score >= min_score:
                scored.append((doc, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]