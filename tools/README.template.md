# VibeFinder AI: An Applied AI Music Agent

> **Base project:** *Music Recommender Simulation* (AI110 Project 3, Module 3).
> **Final project:** AI110 Project 4, *Applied AI System*.

## 1. Original Project (Music Recommender Simulation)

The original **Music Recommender Simulation** (Project 3) was a content-based recommender that scored every song in a
CSV catalog against a hand-written user profile and returned the top-k songs with an explanation of each score. It
supported several ranking modes, a diversity penalty for repeated artists, and optional preferences such as language,
mood tags and instrumentalness, and it came with a model card on bias and weight experiments. Its limitation: users
had to supply an exact profile, and nothing checked whether the output made sense.

## 2. Title and Summary

**VibeFinder AI** turns a plain-English request ("I need to study for my exam, something quiet") into recommendations.
An agent plans a taste profile, **retrieves** listening guidance from a knowledge base, scores the catalog, **self-checks**
the results, and explains its answer with citations to the sources it used.

Why it matters: it shows the full applied-AI loop (retrieve, act, verify, explain) with guardrails, a measured
reliability harness and a complete reasoning trace, and it runs **offline with no API key**, so anyone can reproduce it.

### New AI features (what was added on top of Project 3)

| Feature | Where | What it does |
|---|---|---|
| RAG (multi-source) | `retriever.py`, `planner.py` | BM25 over a markdown knowledge base **and** the song catalog. Retrieved guidance fills missing profile fields (energy, danceability, genre, mood) and a named song seeds "more like X". |
| Agentic workflow | `agent.py` | Plan, retrieve, act, self-check, repair, confidence gate, explain. Every step is traced. |
| Reliability and guardrails | `guardrails.py`, `critic.py` | Input validation, injection blocking, profile sanitising, self-critique with automatic repair, confidence score, human-in-the-loop clarification. |
| Specialisation | `explain.py` | Constrained "DJ Vibe" style (3 sentences, cited, numeric, grounded check) with a few-shot LLM prompt and an offline template, compared to a baseline. |
| Test harness | `evaluate.py`, `tests/` | 13 predefined cases, RAG on/off ablation, style comparison, 28 new unit tests. |

## 3. Architecture Overview

The diagram source is in [`diagrams/architecture.mmd`](diagrams/architecture.mmd) (Mermaid):

```mermaid
{{MERMAID}}
```

**Data flow.** (1) The request passes input guardrails. (2) The retriever searches the knowledge base and the catalog.
(3) The planner extracts what the user explicitly said; retrieved guidance fills only the gaps, so user words always
win. (4) The profile is validated and the scorer ranks candidates. (5) The critic checks for repeated artists, energy
mismatch, genre misses and weak matches, and the agent repairs what it can. (6) A confidence score decides whether to
answer or ask the human a clarifying question. (7) The explainer writes a cited answer and a grounding check verifies it
only mentions real songs and real retrieved sources. (8) Every step is logged to `ai_interactions.md`.
Humans appear in the loop in two places: the clarification question, and the human review of the eval traces.

## 4. Setup Instructions

Requires Python 3.10+. The new system uses only the standard library (`requests` is needed only for the optional
Gemini mode).

```powershell
# Windows PowerShell, from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
# macOS / Linux / Git Bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Then:

```text
python -m src.vibefinder "I need to study for my exam, something quiet"   # one request
python -m src.vibefinder --interactive                                     # asks follow-ups when unsure
pytest -q                                                                  # unit tests
python -m src.vibefinder.evaluate                                          # evaluation harness
```

Useful flags: `--no-rag` (disable retrieval), `--baseline` (plain explanation), `-k 3` (number of songs),
`--scorer project` (try your real Project 3 `recommend_songs`), `--no-trace` (do not append to `ai_interactions.md`).

**Optional LLM mode.** Set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) to let Gemini produce the JSON profile and
the few-shot explanation. Any failure, invalid JSON or ungrounded answer silently falls back to the offline logic.
Force offline with `VIBEFINDER_OFFLINE=1`. In PowerShell: `$env:GEMINI_API_KEY = "your-key"`. Never commit keys;
`.env` is git-ignored.

## 5. Sample Interactions (real output)

Produced by running the system (offline mode, built-in scorer). Step-by-step traces for these runs are in
[`ai_interactions.md`](ai_interactions.md).

```text
{{DEMO}}
```

What these show:
- **RAG changes behaviour.** The studying request infers lofi/focused music from the Studying guide and cites it; with `--no-rag` the same request has no genre, mood or danceability, gets a lower-confidence generic result, and the explanation admits no guide matched.
- **Multi-source retrieval.** "something like Focus Flow" finds the song in the catalog and seeds the profile from it.
- **Guardrails.** The injection attempt is blocked; the gibberish request triggers the human-in-the-loop question instead of a guess.
- **Self-check.** "high energy jazz" is a conflicting request (jazz is calm in this catalog). The critic flags `energy_mismatch`, confidence drops, and the explanation honestly says the match is partial.
- **Specialisation.** The last run uses the plain baseline explanation; compare it with the cited DJ Vibe explanation for the same request earlier.

## 6. Reliability and Evaluation Results

`python -m src.vibefinder.evaluate` (deterministic: offline, built-in scorer):

```text

 python -m src.vibefinder.evaluate                                      
case              expected              got                   conf   result
study             ok                    ok                    0.98   PASS
workout           ok                    ok                    0.96   PASS
party             ok                    ok                    1.00   PASS
sleep             ok                    ok                    1.00   PASS
rainy_jazz        ok                    ok                    1.00   PASS
road_trip_rock    ok                    ok                    0.99   PASS
more_like         ok                    ok                    0.95   PASS
conflict_flagged  ok                    ok                    0.82   PASS
gibberish         needs_clarification   needs_clarification   0.28   PASS
empty             rejected              rejected              0.00   PASS
injection         rejected              rejected              0.00   PASS
too_long          rejected              rejected              0.00   PASS
non_string        rejected              rejected              0.00   PASS

Passed 13/13 | mean confidence (answered): 0.96

RAG ablation (cases that depend on retrieved guidance)
case      RAG on                RAG off               
study     PASS (conf 0.98)      FAIL (conf 0.40)      
workout   PASS (conf 0.96)      FAIL (conf 0.28)      
party     PASS (conf 1.00)      FAIL (conf 0.39)      
sleep     PASS (conf 1.00)      FAIL (conf 0.28)      
RAG on: 4/4 pass | RAG off: 0/4 pass

Explanation style (mean over answered cases)
metric      baseline  specialised 
words       63.9      33.8        
citations   0.0       1.0         
numbers     15.0      4.0         
```

Unit tests: `{{PYTEST}}` (includes the Project 3 tests plus guardrails, catalog loading, scoring, retrieval, planner,
critic, agent end-to-end, LLM failure and ungrounded-LLM handling).

### Human-evaluation table (manual review of the traces in `logs/eval_traces.md`)

| Test input | Evaluation criteria | Result |
|---|---|---|
| "I need to study for my exam, something quiet" | Top 3 calm, focus-friendly, explanation cites a guide | Pass |
| "pump-up music for the gym" | Mean energy >= 0.8, tempo tip cited | Pass |
| "high energy jazz" | Conflict surfaced, not hidden | Pass (flagged `energy_mismatch`) |
| Empty string | Handled gracefully | Pass (blocked, no crash) |
| Prompt-injection text | Not executed | Pass (blocked) |
| "asdfgh qwerty zxcv" | Does not guess | Pass (asks for clarification) |
| Study request with `--no-rag` | Same quality without retrieval? | Fail by design (shows the value of RAG) |

## 7. Design Decisions and Trade-offs

- **Offline-first.** A hand-written BM25 retriever and rule-based planner mean the project reproduces without keys, cost or network. Trade-off: weaker language understanding than an LLM or embeddings, which the optional Gemini mode partly offsets.
- **RAG fills gaps, never overrides.** Explicit user words beat retrieved defaults. Trade-off: "high energy jazz" keeps the user's energy even though jazz guidance says calm; the critic flags it instead of silently "fixing" the user.
- **Wrap the recommender, do not replace it.** `scoring.py` contains a simplified four-feature scorer modeled on Project 3, plus an adapter that tries your real `recommend_songs` (`--scorer project`) and falls back safely. Trade-off: the built-in scorer is simpler than Project 3's (no ranking modes or language/mood-tag features).
- **Critic repairs only what is safe.** It can diversify artists or drop an *inferred* genre, but never a genre the user typed.
- **Grounding check on explanations.** Cited sources and song titles must be real; otherwise the LLM text is discarded for the template.
- **Small catalog (24 songs).** Keeps results inspectable; limits diversity (see the model card).

## 8. Reflection

<<< WRITE 3-4 SENTENCES IN YOUR OWN WORDS: what this project taught you about AI and problem-solving.
Full responsible-AI reflection (AI collaboration, accepted and rejected suggestions, biases, misuse, limitations) is in
[`model_card.md`](model_card.md).

**Portfolio note:** <<< WRITE 2-3 SENTENCES IN YOUR OWN WORDS: what this project says about you as an AI engineer.

## 9. Repository Layout

```text
data/songs.csv                 sample song catalog used by VibeFinder
data/songs_project3.csv        original Project 3 catalog (used by the Project 3 tests)
data/knowledge/*.md            RAG knowledge base (activities, genres, moods)
src/recommender.py, main.py    original Project 3 code (unchanged)
src/vibefinder/                guardrails, retriever, planner, scoring, critic, explain, agent, CLI, evaluate
tests/                         Project 3 tests and test_vibefinder.py
diagrams/architecture.mmd      Mermaid source of the architecture diagram
ai_interactions.md             saved agent reasoning traces
model_card.md                  reflection, ethics, baseline vs specialised comparison
tools/build_docs.py            regenerates README/model card with real outputs
logs/                          eval_results.json, eval_traces.md (runtime log is git-ignored)
```

## 10. Stretch Features Checklist

- RAG enhancement: knowledge base plus song-catalog retrieval, before/after in section 5 and `model_card.md`.
- Agentic workflow enhancement: multi-step plan/act/check/repair chain; traces saved in `ai_interactions.md`.
- Specialisation: DJ Vibe style vs baseline, measured in `model_card.md`.
- Test harness: `python -m src.vibefinder.evaluate` with a pass/fail and confidence summary.