# AI Interactions Log

## Agentic Workflow (SF8)

**What task did you give the agent?**

I asked Claude (in a chat window) to work through the whole Music
Recommender project with me, including every optional stretch feature. For
this stretch feature the task was: add more song attributes to the dataset
and update the scoring so the new attributes affect the recommendations.
Claude wrote the code and also ran it in its own sandbox before giving it to
me. I ran everything again on my machine (Windows, VS Code, Python 3.14,
a venv) and pasted back errors and outputs.

**Prompts used:**

- "I want us to work meticulously on this project" (with the full assignment
  and rubric pasted in)
- "we do everything even the optional"
- "I mean you should be providing the solutions"
- "Continue" / "go" (to move on to each next stretch feature)

**What did the agent generate or change?**

- `data/songs.csv`: expanded from 10 to 24 songs and added five new columns:
  `popularity`, `release_decade`, `mood_tags`, `language`, `instrumentalness`.
- `src/recommender.py`: scoring now also uses `acousticness`,
  `instrumentalness`, `popularity`, `release_decade`, `mood_tags` and
  `language`. These are optional: a feature is scored only when the listener
  profile gives a preference for it, so older profiles score exactly as before.
- `src/main.py`: a new "Rainy Study Session" profile that uses the extras.
- `tests/test_recommender.py`: three new tests (instrumental preference,
  language match, mood-tag overlap).
- `README.md` and `model_card.md`:
---

## Run 2026-11-07 14:32:36

**Query:** `I need to study for my exam, something quiet`  
**Status:** ok | **Confidence:** 0.98 | **RAG:** on | **Scorer:** builtin | **LLM:** offline

**Reasoning trace**

1. **validate_input** - `{"ok": true, "reason": ""}`
2. **retrieve_knowledge** - `{"enabled": true, "hits": [["activities#Studying", 9.53]]}`
3. **enrich_profile** - `{"notes": ["danceability=0.425 from activities#Studying", "genre=lofi from activities#Studying", "mood=focused from activities#Studying"]}`
4. **plan** - `{"profile": {"genre": "lofi", "mood": "focused", "energy": 0.2, "danceability": 0.425, "activity": "Studying", "seed_song": null, "sources": {"energy": "user", "danceability": "activities#Studying", "genre": "activities#Studying", "mood": "activities#Studying"}}}`
5. **score_catalog** - `{"scorer": "builtin", "top3": [["Library Rain", 5.04], ["Focus Flow", 5.03], ["Rainy Window Beats", 4.12]]}`
6. **self_check** - `{"issues": []}`
7. **self_check_after_repair** - `{"issues": []}`
8. **confidence** - `{"score": 0.98, "threshold": 0.4}`
9. **explain** - `{"style": "specialised", "grounded": true, "metrics": {"words": 33, "citations": 1, "numbers": 4}}`

**Final recommendations**

1. Library Rain - Paper Lanterns (lofi/focused, score 5.04)
2. Focus Flow - LoRoom (lofi/focused, score 5.03)
3. Rainy Window Beats - Paper Lanterns (lofi/moody, score 4.12)
4. Midnight Coding - LoRoom (lofi/chill, score 3.98)
5. Quiet Piano Hours - Elena Voss (classical/focused, score 3.29)

**Explanation:** Steady tempo and few surprises keep working memory free; avoid high-energy tracks [activities#Studying]. "Library Rain" by Paper Lanterns has energy 0.40, inside the 0.20-0.45 range and danceability 0.58. Keep "Focus Flow" queued next.
