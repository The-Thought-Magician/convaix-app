# Codebase Audit

Snapshot of `convaix/` and `VectorDatabaseBook/ch8/` as of 2026-04-29, with
explicit gaps to address.

## convaix (Python package, src layout)

### Files (962 lines of source, 505 lines of tests)

| Module | Lines | Status |
| --- | --- | --- |
| `src/convaix/schema.py` | 121 | Solid — schema v1.0 contract, conv_id, x-convaix |
| `src/convaix/validate.py` | 48 | Solid — schema validator |
| `src/convaix/db.py` | 287 | Solid — SQLite + sqlite-vec, snapshots/chunks tables |
| `src/convaix/search.py` | 158 | Solid — hybrid kw + semantic search |
| `src/convaix/chunking.py` | 23 | Solid — paragraph chunking |
| `src/convaix/embeddings.py` | 56 | **Apple-only** — uses MLX (nomic-embed-text-v1.5, 768-dim) |
| `src/convaix/cli.py` | 266 | Solid — load / list / search / validate / history / export |
| `src/convaix/providers/__init__.py` | 1 | **EMPTY STUB** — docstring only |
| `src/convaix/exchange/__init__.py` | 1 | **EMPTY STUB** — "git-based exchange" placeholder |

### Schema v1.0 (the contract)

```
{
  "schema_version": "1.0",
  "conversation": {
    "id": "conv_<sha256[:12]>",       // stable: hash(source:source_id)
    "title": "...",
    "source": "claude" | "chatgpt" | "gemini" | ...,
    "source_id": "<provider's own id>",
    "source_url": "...",              // optional
    "model": "claude-3-5-sonnet-20241022",
    "created_at": "ISO-8601",
    "exported_at": "ISO-8601",
    "tags": [],
    "metadata": {}
  },
  "turns": [
    {
      "turn_number": 1,                // 1-indexed
      "role": "user" | "assistant" | "system",
      "content": "...",
      "timestamp": "ISO-8601",
      "attachments": [],
      "metadata": {}
    }
  ],
  "statistics": { "turn_count": ..., "user_turns": ..., "assistant_turns": ..., "total_chars": ... },
  "x-convaix": {                       // optional extension block
    "convaix_id": "cx_<uuid4>",        // globally unique snapshot id
    "version": "0.1",
    "conv_id": "conv_...",             // same as conversation.id
    "author": { "handle": "...", "key_id": null },
    "published_at": "ISO-8601",
    "parent_refs": [],                 // for snapshot lineage
    "annotations": [],
    "signature": null
  }
}
```

This is genuinely useful and reusable. Don't break it.

### SQLite tables (already in `db.py`)

- `snapshots` — one row per `convaix_id` (snapshot of a `conv_id`)
- `chunks` — paragraph-level text chunks per snapshot
- `chunks_vec` — virtual table (sqlite-vec, 768-dim float)
- `discussions`, `discussion_refs`, `discussion_messages` — for the
  social-network / shared-discussion idea (not yet wired to UI)

### Gaps in convaix

1. No provider parsers. `providers/` is empty. The CLI's `load` accepts
   already-converted v1.0 JSON — it cannot read raw Claude/ChatGPT/Gemini
   exports.
2. No PostgreSQL backend.
3. No web UI.
4. Embedding model is Apple-only (mlx-embedding-models). Need a
   cross-platform fallback for Linux/Windows users.
5. `exchange/` (git-based hub) is a placeholder.
6. No RAG / chat-over-imports.

## VectorDatabaseBook/ch8/app.py (single file, 966 lines)

### What it does

- PostgreSQL + pgvector + pg_trgm, HNSW indexes
- ThreadedConnectionPool
- `EmbeddingGenerator` — sentence-transformers (`all-MiniLM-L6-v2`, 384-dim,
  cross-platform)
- `DocumentIngester` — chunk + embed + upsert
- `SearchEngine` — hybrid (semantic + ts_rank)
- `ConversationManager` — sessions / messages / message embeddings
- `OllamaClient` — generate + chat against local Ollama
- `ConversationRAG` — orchestrates retrieve → prompt → generate
- FastAPI app with HTMX endpoints (`/htmx/ask`) and JSON API
- CLI: `setup` / `load-samples` / `serve [port]`

### Gaps in ch8 vs the goal

1. Schema is **document-centric**, not conversation-import-centric.
   `documents`/`document_chunks` tables would map to convaix's
   `snapshots`/`chunks`, but field names and dimensions differ.
2. Sessions/messages are *new RAG sessions*, not *imported LLM conversations*.
   We need imported conversations to live in the same vector store as RAG
   targets — i.e. each Claude/ChatGPT/Gemini conversation should be
   searchable both as content (RAG source) and as a conversation (browsable).
3. No provider parsers (same gap as convaix).
4. Embedding dim is 384, convaix uses 768. Pick one and standardize.
5. Hardcoded DB password / config — fine for the book, not for shipping.

## What we keep from each repo

| From convaix | From ch8 |
| --- | --- |
| Schema v1.0 + validator | FastAPI + HTMX scaffold |
| `conv_id` / `convaix_id` model | Connection pool pattern |
| SQLite + sqlite-vec adapter | pgvector + HNSW indexes |
| Hybrid keyword/semantic search shape | `OllamaClient` + RAG prompt format |
| CLI structure (click + rich) | `ConversationRAG.ask()` flow |
| Test layout | Sample-data loader pattern |

## What we throw away

- ch8's `documents` / `document_chunks` schema — replaced by convaix snapshots/chunks
- ch8's hardcoded 384-dim — picked once at architecture level
- convaix's MLX-only embedder *as the default* — kept as an opt-in fast path on Mac

## Risks identified

1. **Provider export formats are not stable** — Claude's export JSON, OpenAI's
   conversations.json, and Google Takeout's Gemini format have all changed
   shape over the past 18 months. Code defensively; capture raw blob in
   `metadata` for re-parse.
2. **ChatGPT export uses a tree (`mapping`), not a list** — must walk parent
   pointers to linearize turns. Branches will be lossy if flattened.
3. **Gemini export is the weakest** — Google Takeout often gives HTML or
   per-prompt logs without conversation grouping. May need
   workspace-account API access or a browser extension as fallback.
4. **Embedding model choice locks DB schema** — vector dimension is part of
   the schema. Changing it later means re-embedding everything.
5. **Apple Silicon vs cross-platform embedding** — convaix's MLX path is
   great on Mac but useless on Linux/Windows. Need a portable default.
