"""VibeAgent: plan -> retrieve -> act -> self-check -> explain."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import critic, explain, planner
from .catalog import vocabulary
from .guardrails import validate_query
from .retriever import Doc, Retriever, load_knowledge, songs_to_docs
from .scoring import max_possible, score_catalog
from .tracing import Trace

logger = logging.getLogger("vibefinder.agent")

CONFIDENCE_THRESHOLD = 0.40
CLARIFY_QUESTION = ("I'm not sure what you're after. Tell me an activity "
                    "(studying, workout, party...), a mood, or a genre.")


def configure_logging(log_dir: str | Path) -> None:
    """Send INFO logs to logs/vibefinder.log and warnings to the console."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("vibefinder")
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_dir / "vibefinder.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root.addHandler(file_handler)
    root.addHandler(console)


@dataclass
class AgentResult:
    """Everything the agent produced for one query."""

    query: str
    status: str = "ok"  # ok | rejected | needs_clarification
    reason: str = ""
    profile: Optional[planner.Profile] = None
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    baseline: str = ""
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)
    retrieved: List[Tuple[str, float]] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    clarification: str = ""
    scorer: str = "-"
    llm_name: str = "offline"
    use_rag: bool = True


class VibeAgent:
    """Agentic music recommender with retrieval, guardrails and self-checks."""

    def __init__(self, songs: List[dict], knowledge_dir: str | Path, llm=None,
                 use_rag: bool = True, specialised: bool = True,
                 scorer: Optional[str] = None, k: int = 5,
                 threshold: float = CONFIDENCE_THRESHOLD) -> None:
        self.songs, self.llm = songs, llm
        self.use_rag, self.specialised = use_rag, specialised
        self.scorer, self.k, self.threshold = scorer, k, threshold
        self.genres, self.moods = vocabulary(songs)
        self.knowledge = Retriever(load_knowledge(knowledge_dir))
        self.catalog_index = Retriever(songs_to_docs(songs))

    # ------------------------------------------------------------------
    def run(self, query: object) -> AgentResult:
        """Run the full pipeline for one user query."""
        trace = Trace()
        result = AgentResult(query=str(query), use_rag=self.use_rag,
                             llm_name=getattr(self.llm, "name", "offline"))
        try:
            self._run(query, result, trace)
        except Exception as err:  # last-resort guardrail: never crash the user
            logger.exception("Unexpected agent failure")
            result.status, result.reason = "rejected", f"Internal error: {err}"
            trace.add("error", message=str(err))
        result.trace = trace.steps
        logger.info("query=%r status=%s confidence=%.2f issues=%s", result.query,
                    result.status, result.confidence, result.issues)
        return result

    def _run(self, query: object, result: AgentResult, trace: Trace) -> None:
        check = validate_query(query)
        trace.add("validate_input", ok=check.ok, reason=check.reason)
        if not check.ok:
            result.status, result.reason = "rejected", check.reason
            return
        text = check.cleaned
        result.query = text

        # 1. Retrieve (multi-source) ------------------------------------
        docs: List[Doc] = []
        if self.use_rag:
            hits = self.knowledge.search(text, k=3, source="knowledge")
            docs = [d for d, _ in hits]
            result.retrieved = [(d.doc_id, round(s, 2)) for d, s in hits]
        trace.add("retrieve_knowledge", enabled=self.use_rag, hits=result.retrieved)

        # 2. Plan -------------------------------------------------------
        profile = planner.rule_based_parse(text, self.genres, self.moods)
        if self.llm is not None:
            llm_profile = planner.llm_parse(self.llm, text, docs, self.genres, self.moods)
            if llm_profile is not None:
                for name in ("genre", "mood", "energy", "danceability"):
                    if getattr(profile, name) is None:
                        setattr(profile, name, getattr(llm_profile, name))
                        if getattr(llm_profile, name) is not None:
                            profile.sources[name] = "llm"
        if self.use_rag:
            seed = planner.find_seed_song(text, self.songs)
            if seed is not None:
                trace.add("retrieve_song", seed=planner.apply_seed(profile, seed))
            notes = planner.enrich_from_docs(profile, docs, self.genres, self.moods)
            trace.add("enrich_profile", notes=notes)
        result.profile = profile
        trace.add("plan", profile=profile.describe())

        # 3. Act: score the catalog with the Project 3 recommender ---------
        prefs = profile.to_prefs()
        scored, used = score_catalog(prefs, self.songs, self.k * 4, self.scorer)
        result.scorer = used
        trace.add("score_catalog", scorer=used, top3=[
            (s["title"], round(sc, 2)) for s, sc, _ in scored[:3]])

        # 4. Self-check + repair ----------------------------------------
        max_score = max_possible(prefs)
        issues = critic.critique(scored, prefs, profile.sources.get("genre", ""),
                                 self.k, max_score)
        trace.add("self_check", issues=issues)
        if "artist_repeat" in issues:
            scored = critic.diversify(scored, len(scored))
            trace.add("repair", action="diversified artists")
        if "weak_match" in issues and profile.genre and profile.sources.get("genre") != "user":
            dropped = profile.genre
            profile.genre = None
            profile.sources.pop("genre", None)
            prefs = profile.to_prefs()
            scored, used = score_catalog(prefs, self.songs, self.k * 4, self.scorer)
            max_score = max_possible(prefs)
            trace.add("repair", action=f"dropped inferred genre '{dropped}' and re-ranked")
        issues = critic.critique(scored, prefs, profile.sources.get("genre", ""),
                                 self.k, max_score)
        trace.add("self_check_after_repair", issues=issues)
        result.issues = issues
        top = scored[: self.k]
        result.recommendations = [{"song": s, "score": sc, "reasons": r}
                                  for s, sc, r in top]

        # 5. Confidence + human-in-the-loop -------------------------------
        retrieval_part = 0.0
        if result.retrieved:
            retrieval_part = min(1.0, result.retrieved[0][1] / 6.0)
        ratio = (top[0][1] / max_score) if top and max_score else 0.0
        result.confidence = round(
            0.5 * profile.known_fields() / 4 + 0.2 * retrieval_part + 0.3 * min(1.0, ratio), 2)
        trace.add("confidence", score=result.confidence, threshold=self.threshold)
        if result.confidence < self.threshold:
            result.status, result.clarification = "needs_clarification", CLARIFY_QUESTION
            result.recommendations = []
            trace.add("human_in_the_loop", question=CLARIFY_QUESTION)
            return

        # 6. Explain ------------------------------------------------------
        result.baseline = explain.baseline_explanation(top)
        special = None
        if self.llm is not None and self.specialised:
            special = explain.llm_explanation(self.llm, top, profile, docs)
        if special is None:
            special = explain.specialised_explanation(top, profile, docs, issues)
        result.explanation = special if self.specialised else result.baseline
        ids = [d.doc_id for d in docs]
        trace.add("explain", style="specialised" if self.specialised else "baseline",
                  grounded=explain.grounded(result.explanation, top, ids)
                  if self.specialised else None,
                  metrics=explain.metrics(result.explanation))