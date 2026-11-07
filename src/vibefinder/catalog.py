"""Song catalog loading (the data source from the original Music Recommender)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger("vibefinder.catalog")

NUMERIC_FIELDS = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")
REQUIRED_FIELDS = ("title", "artist", "genre", "mood", "energy", "danceability")

Song = Dict[str, object]


def load_songs(path: str | Path) -> List[Song]:
    """Load songs from a CSV file, skipping malformed rows safely.

    Args:
        path: Path to the songs CSV file.

    Returns:
        A list of song dictionaries with numeric fields converted to floats.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no valid songs could be loaded.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Song catalog not found: {path}")
    songs: List[Song] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            song = {k: (v or "").strip() for k, v in row.items() if k}
            try:
                for name in NUMERIC_FIELDS:
                    if name in song and song[name] != "":
                        song[name] = float(song[name])
                missing = [f for f in REQUIRED_FIELDS if song.get(f) in (None, "")]
                if missing:
                    raise ValueError(f"missing fields {missing}")
            except ValueError as err:
                logger.warning("Skipping row %d in %s: %s", line_no, path, err)
                continue
            song["genre"] = str(song["genre"]).lower()
            song["mood"] = str(song["mood"]).lower()
            songs.append(song)
    if not songs:
        raise ValueError(f"No valid songs found in {path}")
    logger.info("Loaded %d songs from %s", len(songs), path)
    return songs


def vocabulary(songs: List[Song]) -> Tuple[Set[str], Set[str]]:
    """Return the (genres, moods) that actually exist in the catalog."""
    genres = {str(s["genre"]) for s in songs}
    moods = {str(s["mood"]) for s in songs}
    return genres, moods