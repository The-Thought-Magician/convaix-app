# Roadmap

Six milestones. M0 is setup; M1–M3 are the demo; M4–M5 are polish + ship.

| # | Milestone | Goal | Done when |
| - | --- | --- | --- |
| M0 | Setup & spike | Repo running locally on both backends; baseline tests green | `pytest -m "not slow"` passes; PG dev DB stands up via docker-compose |
| M1 | Provider parsers | Import Claude / ChatGPT / Gemini exports → schema v1.0 JSON | `convaix import claude/chatgpt/gemini <file>` writes valid snapshots into the SQLite store |
| M2 | Postgres backend | Same loader works against pgvector | `convaix import ... --db postgresql://...` round-trips; `convaix search` returns ranked hits |
| M3 | Web UI on convaix schema | Browse / search imported conversations in a browser | FastAPI app shows imported conversations, lets you search and click into a thread |
| M4 | RAG over imports | Ask questions, get cited answers from your own corpus | `/api/ask?q=...` returns Ollama-generated answers grounded in retrieved chunks; HTMX UI shows sources |
| M5 | Desktop packaging | One-click downloadable app | macOS `.dmg` and Windows `.exe` (or single Tauri bundle) launches, embeds DB + Ollama, no terminal needed |

## Demo target (= end of M3)

> "Drag your Claude / ChatGPT / Gemini export file onto a window. See all your
> past conversations in one searchable list. Click into any thread. Find
> stuff."

That's enough to put in front of someone and have a real conversation about
the product. M4 (RAG) makes it *interesting*; M5 makes it *shippable*.

## Suggested ordering & sizing

| Milestone | Rough size | Sequence |
| --- | --- | --- |
| M0 | 1 day  | sequential |
| M1 | 3-5 days | parsers can be done in parallel after `base.py` lands |
| M2 | 2-3 days | depends on M0 docker-compose; not on M1 |
| M3 | 2-4 days | depends on M2; UI work is the bulk |
| M4 | 2-3 days | depends on M3 |
| M5 | 1-2 weeks | last; lots of platform fiddling |

M1 and M2 can overlap — Postgres backend doesn't need real importers, it can
develop against the existing v1.0 sample JSON in `convaix/tests/`.

## Definition of "demo-ready"

End of M3, user can:

1. Run a single command (or click an installer) to start the app.
2. Drop a Claude export, a ChatGPT export, and a Gemini Takeout in.
3. See a unified list of conversations with source badges (claude / chatgpt / gemini).
4. Type a query, get hits across all three.
5. Click a hit, see the full conversation rendered.

Everything beyond that is a bonus.

## Risk budget

- **M1 will slip if export formats are weirder than expected.** Mitigation:
  build `claude` first (best-documented), then `chatgpt`, then `gemini` last
  (worst format). Stub Gemini behind a "best-effort" flag if Takeout JSON
  isn't conversation-grouped.
- **M5 packaging is open-ended.** Don't start it until M3 is solid. The
  conversation already says "too far down the line".
