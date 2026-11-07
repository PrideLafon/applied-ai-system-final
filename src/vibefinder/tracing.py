"""Reasoning-trace logging: every agent step is saved to a markdown file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

HEADER = (
    "# AI Interactions Log\n\n"
    "Every agent run appends a trace here: the plan, retrieval results, "
    "guardrail events, self-check findings and the final answer.\n"
)


class Trace:
    """An ordered list of agent steps."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []

    def add(self, name: str, **detail: Any) -> None:
        """Record one step."""
        self.steps.append({"step": len(self.steps) + 1, "name": name, **detail})


def append_markdown(result, path: str | Path) -> None:
    """Append a readable trace for `result` to a markdown file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(HEADER, encoding="utf-8")
    lines = [f"\n---\n\n## Run {datetime.now():%Y-%m-%d %H:%M:%S}\n",
             f"**Query:** `{result.query}`  ",
             f"**Status:** {result.status} | **Confidence:** {result.confidence:.2f} "
             f"| **RAG:** {'on' if result.use_rag else 'off'} "
             f"| **Scorer:** {result.scorer} | **LLM:** {result.llm_name}\n",
             "**Reasoning trace**\n"]
    for step in result.trace:
        detail = {k: v for k, v in step.items() if k not in ("step", "name")}
        lines.append(f"{step['step']}. **{step['name']}** - "
                     f"`{json.dumps(detail, default=str)}`")
    if result.recommendations:
        lines.append("\n**Final recommendations**\n")
        for i, rec in enumerate(result.recommendations, 1):
            s = rec["song"]
            lines.append(f"{i}. {s['title']} - {s['artist']} "
                         f"({s['genre']}/{s['mood']}, score {rec['score']:.2f})")
    if result.explanation:
        lines.append(f"\n**Explanation:** {result.explanation}")
    if result.reason:
        lines.append(f"\n**Reason:** {result.reason}")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")