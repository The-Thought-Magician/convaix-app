# Plan — convaix + Ch8 Web App

Project plan for combining `convaix` (common conversation schema + SQLite store) with
`VectorDatabaseBook/ch8` (FastAPI + pgvector + Ollama RAG) into a single
downloadable app that imports conversations from Claude, ChatGPT, and Gemini,
unifies them in a vector store, and lets you search and chat over them.

## North star (per Nitin's chat, 28-29 Apr 2026)

> Combine ch8's parsing/upload + database schema with convaix and generalize to
> all three LLMs. First make it work on Postgres, then on SQLite3 — both with a
> vector extension. Packaging (Tauri / desktop) comes later. Get it working,
> demo it.

## Folder map

| File | Purpose |
| --- | --- |
| `codebase-audit.md` | What exists today in convaix and ch8, with gap analysis |
| `architecture.md` | Target architecture: schema contract, layers, DB choices |
| `roadmap.md` | Milestones M0..M5 with goals and definition of done |
| `milestone-1-providers.md` | Provider parsers (Claude / ChatGPT / Gemini) |
| `milestone-2-pg-backend.md` | PostgreSQL + pgvector backend |
| `milestone-3-webapp.md` | FastAPI + HTMX UI on convaix schema |
| `milestone-4-rag.md` | RAG / chat over imported conversations |
| `milestone-5-packaging.md` | Desktop packaging (Tauri / PyInstaller / pywebview) |
| `open-questions.md` | Decisions to confirm on the Thursday call |

## Working principles

1. **Demo first, package later.** Nitin's call: get it working end-to-end, then
   worry about packaging. Don't bikeshed Tauri vs Electron yet.
2. **convaix schema v1.0 is the contract.** Already defined and validated.
   Everything else (parsers, DB writers, web UI) maps to it.
3. **Postgres before SQLite.** Explicit ordering. Both share the convaix schema;
   only the storage adapter differs.
4. **Reuse, don't rewrite.** convaix already has parsing/db/search foundations;
   ch8 has FastAPI/RAG/Ollama. We are gluing, not greenfield-ing.
5. **The empty `providers/` package is the critical missing piece.** Nothing
   downstream works without provider parsers.

## Repo layout the plan assumes

We will do most of the work *inside* the existing `convaix/` repo, extending
its `providers/`, `exchange/`, and `db.py` modules, plus adding a `web/`
sibling to `cli.py`. The ch8 app remains as reference / source of design; we
copy patterns from it, not files.

`VectorDatabaseBook/` is a read-only reference repo; we should not commit
into it.
