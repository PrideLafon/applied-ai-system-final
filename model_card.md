# Model Card: VibeFinder AI

## Model Overview

- **Name:** VibeFinder AI (extension of the Music Recommender Simulation, Project 3)
- **Type:** Retrieval-augmented, agentic recommender. Ranking is a transparent weighted scorer (genre 2.0, mood 1.0,
  energy 1.5 x closeness, danceability 1.0 x closeness); the AI components are retrieval (BM25), planning,
  self-critique and explanation. An LLM (Gemini) is optional, not required.
- **Intended use:** Classroom demonstration of an applied AI pipeline on a 24-song fictional catalog.
- **Not intended for:** Real music streaming, profiling people, or any decision about a person.

## Evaluation Summary

| Check | Result |
|---|---|
| Harness cases passed (`python -m src.vibefinder.evaluate`) | 13 / 13 |
| Mean confidence on answered requests | 0.96 |
| Unit tests (`pytest -q`) | 41 passed in 0.36s |
| RAG on vs off, context-dependent cases | 4 / 4 vs 0 / 4 pass |

### Baseline vs specialised explanation (measured, mean over the answered cases)

| Metric | Baseline (plain scorer reasons) | Specialised (DJ Vibe) |
|---|---|---|
| Words | 63.9 | 33.8 |
| Citations to retrieved guide | 0 | 1 |
| Decimal numbers quoted | 15 | 4 |
| Grounding check (real songs, real sources only) | not applicable | enforced; ungrounded text is discarded |

The specialised style is shorter and always cites its source, but it quotes fewer numbers. That is a real trade-off:
the baseline is more detailed for someone who wants the raw score components.

### Before/after retrieval example

Request: "I need to study for my exam, something quiet".

- **Without retrieval:** profile = energy 0.2 only; top pick *Dream Tide* (ambient); results mix ambient, jazz and
  classical; confidence 0.40; the explanation says no guide matched.
- **With retrieval:** the Studying guide adds lofi, focused and danceability 0.425; top pick *Library Rain*
  (lofi/focused); confidence 0.98; the explanation cites `[activities#Studying]`. <<< CHECK THESE MATCH THE OUTPUT IN YOUR README SECTION 5

## Limitations and Biases

- **Tiny, invented catalog.** 24 songs, 9 genres. Genres with one or two songs (hip hop, classical) are over- or
  under-served depending on the query, and any "taste" it learns is the taste of whoever wrote the CSV.
- **Simplified scorer.** The built-in scorer uses four features; Project 3's richer features (ranking modes, language,
  mood tags, instrumentalness) are not used in this pipeline, so results are less nuanced than the original.
- **Western-genre bias.** Genres, moods and the knowledge base reflect mainstream Western categories; there is no
  Afrobeats, makossa, bikutsi, gospel or other regional music. Users asking for them get nothing relevant, and the
  system would not know why.
- **The knowledge base encodes opinions.** "Studying means low energy" is a generalisation; some people focus best with
  fast music. Retrieval presents this as guidance, but it is one author's view.
- **Exact-match mood and genre.** The scorer gives full points only for exact labels, so near-misses (indie pop vs
  pop) get nothing.
- **Keyword retrieval.** BM25 matches words, not meaning. Negation ("not jazz") and sarcasm are not understood, and
  "high energy jazz" pulled a relaxed mood from the Jazz guide even though the user wanted energy.
- **Conflicts are flagged, not solved.** The critic reports `energy_mismatch`; it does not search for a better compromise.
- **English only**, and the offline planner only knows a fixed vocabulary.

## Misuse Potential and Prevention

- **Prompt injection** (trying to make the system reveal prompts or keys): blocked by pattern guardrails. The
  guardrail is a list of patterns, so a novel phrasing could slip through. Mitigations: the offline path never
  executes user text, LLM output is parsed as JSON and validated against the catalog, and keys are only read from
  environment variables and never logged.
- **LLM hallucination:** ungrounded explanations (unknown songs or sources) are rejected by `grounded()` and replaced.
- **Input abuse:** length and character limits prevent oversized or binary input.
- **Manipulation risk if deployed at scale:** a recommender can nudge listening habits or favour paying artists. This
  version has no commercial signals; a real deployment should publish its ranking weights and audit diversity.

## What Surprised Me While Testing Reliability

<<< REPLACE OR KEEP, BUT ONLY KEEP ITEMS THAT REALLY HAPPENED TO YOU. These three really happened while this system was built:
1. Removing retrieval did not just lower quality; every context-dependent case went from passing to failing, and some
   fell below the confidence threshold so the system would ask a question instead of guessing.
2. My first retrieval returned the wrong guide for "high energy jazz" because words like "energy" appear in every guide
   as a field label. Adding those labels to the stopword list fixed it. Retrieval bugs look like AI bugs.
3. My first stemmer turned "studying" into "study" but "study" into "stud", so the same word did not match itself.
   A unit test caught it.

## AI Collaboration

**How I used AI:** <<< EDIT. Example: I used Claude to plan the extension, generate the first version of the modules, and debug errors. I gave it the assignment page and rubric, then ran everything myself, read the output, and decided what to keep.

**One suggestion I accepted:** The AI proposed a *critic step that can repair results automatically* (diversify artists, drop an inferred genre). <<< KEEP ONLY IF TRUE FOR YOU, and add why: it made the guardrail change behaviour rather than just print a warning.

**One suggestion I revised or rejected:** <<< WRITE YOUR OWN. Options that fit this build, if they are true for you: (a) the AI made the Gemini API required and I made the system offline-first so it reproduces without a key; (b) the AI let retrieved guidance override words in the request and I changed it so explicit user words always win; (c) the AI's first stemmer and stopword list had bugs that tests exposed and I fixed them; (d) I replaced the AI's claim that the built-in scorer was a "faithful port" of Project 3 with an honest description. Say why you changed it (over-engineered, harder to read, poor fit, or scoped down).

**What I would do differently:** <<< EDIT. Example: write the evaluation cases before the code, and read every trace instead of only the summary.

## Future Improvements

- Replace BM25 with embeddings and compare retrieval quality in the harness.
- Use the full Project 3 scorer with an extended catalog (ranking modes, language, mood tags).
- Soft genre matching (indie pop is close to pop) and a larger, more diverse catalog including African genres.
- Let the critic try compromise profiles for conflicting requests.
- Add user feedback (thumbs up/down) so the system can learn preferences across sessions.
- A larger human evaluation with several listeners instead of one reviewer.