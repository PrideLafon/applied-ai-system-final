"""Command-line interface: python -m src.vibefinder "your request"."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import AgentResult, VibeAgent, configure_logging
from .catalog import load_songs
from .llm import get_llm
from .tracing import append_markdown

ROOT = Path(__file__).resolve().parents[2]


def format_result(result: AgentResult) -> str:
    """Human-readable console output."""
    out = [f"Query: {result.query}"]
    if result.status == "rejected":
        out.append(f"[BLOCKED] {result.reason}")
        return "\n".join(out)
    p = result.profile
    if p:
        out.append(f"Profile: genre={p.genre} mood={p.mood} energy={p.energy} "
                   f"danceability={p.danceability} activity={p.activity}")
    out.append("Retrieved: " + (", ".join(f"{d} ({s})" for d, s in result.retrieved)
                                or "none"))
    out.append(f"Confidence: {result.confidence:.2f} | Self-check issues: "
               f"{result.issues or 'none'}")
    if result.status == "needs_clarification":
        out.append(f"[NEEDS CLARIFICATION] {result.clarification}")
        return "\n".join(out)
    out.append(f"\n{'#':<3}{'Title':<22}{'Artist':<16}{'Genre':<11}{'Mood':<10}Score")
    for i, rec in enumerate(result.recommendations, 1):
        s = rec["song"]
        out.append(f"{i:<3}{str(s['title']):<22}{str(s['artist']):<16}"
                   f"{str(s['genre']):<11}{str(s['mood']):<10}{rec['score']:.2f}")
    out.append(f"\n{result.explanation}")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="VibeFinder AI music agent")
    parser.add_argument("query", nargs="?", help="what you want to listen to")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("-k", type=int, default=5, help="number of songs")
    parser.add_argument("--no-rag", action="store_true", help="disable retrieval")
    parser.add_argument("--baseline", action="store_true",
                        help="plain explanation instead of DJ Vibe style")
    parser.add_argument("--scorer", choices=["builtin", "project"], default=None)
    parser.add_argument("--no-trace", action="store_true",
                        help="do not append to ai_interactions.md")
    args = parser.parse_args(argv)
    if not args.query and not args.interactive:
        parser.error("give a query or use --interactive")

    configure_logging(ROOT / "logs")
    songs = load_songs(ROOT / "data" / "songs.csv")
    agent = VibeAgent(songs, ROOT / "data" / "knowledge", llm=get_llm(),
                      use_rag=not args.no_rag, specialised=not args.baseline,
                      scorer=args.scorer, k=args.k)

    def handle(query: str) -> None:
        result = agent.run(query)
        print(format_result(result))
        if not args.no_trace:
            append_markdown(result, ROOT / "ai_interactions.md")
        if result.status == "needs_clarification" and sys.stdin.isatty():
            extra = input("\nMore detail? > ").strip()
            if extra:
                handle(f"{query} {extra}")

    if args.query:
        handle(args.query)
    while args.interactive:
        try:
            query = input("\nWhat do you want to listen to? (q to quit) > ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "quit", "exit"):
            break
        handle(query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
