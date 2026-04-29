# Target Architecture

## Layered view

```
┌──────────────────────────────────────────────────────────────┐
│  UI                                                          │
│  ├─ CLI  (click, today's `convaix` command)                  │
│  └─ Web  (FastAPI + HTMX, ported from ch8)                   │
├──────────────────────────────────────────────────────────────┤
│  Application                                                 │
│  ├─ Importer       parsers → schema v1.0 → loader            │
│  ├─ Search         hybrid (kw + vec)                         │
│  └─ RAG            retrieve → prompt → Ollama (or other LLM) │
├──────────────────────────────────────────────────────────────┤
│  Domain (the contract)                                       │
│  ├─ schema.py          v1.0 conversation envelope            │
│  ├─ validate.py        schema validator                      │
│  └─ chunking.py        paragraph chunker                     │
├──────────────────────────────────────────────────────────────┤
│  Adapters                                                    │
│  ├─ providers/         claude, chatgpt, gemini parsers       │
│  ├─ embeddings/        mlx (mac) | st (portable) | api       │
│  └─ db/                pg backend | sqlite backend           │
└──────────────────────────────────────────────────────────────┘
```

## Module layout (proposed extension of `convaix/`)

```
src/convaix/
├── __init__.py
├── schema.py              [keep]
├── validate.py            [keep]
├── chunking.py            [keep]
├── search.py              [refactor: backend-agnostic]
├── cli.py                 [extend: import sub-commands]
│
├── providers/             [NEW — fill the empty stub]
│   ├── __init__.py        registry: name → parser class
│   ├── base.py            ProviderParser ABC
│   ├── claude.py          parse Anthropic export JSON
│   ├── chatgpt.py         parse OpenAI conversations.json
│   └── gemini.py          parse Google Takeout (HTML or JSON)
│
├── embeddings/            [refactor: split by backend]
│   ├── __init__.py        get_embedder(name) factory
│   ├── base.py            Embedder ABC (encode, encode_query, dim)
│   ├── mlx_nomic.py       current MLX path (768-dim)
│   ├── sentence_tf.py     sentence-transformers (default, portable)
│   └── api.py             optional: OpenAI / Voyage / Cohere API
│
├── db/                    [NEW — split SQLite + add Postgres]
│   ├── __init__.py        get_store(url) factory
│   ├── base.py            Store ABC
│   ├── sqlite_store.py    moved from db.py + sqlite-vec
│   └── pg_store.py        new — pgvector + HNSW + pg_trgm
│
├── rag/                   [NEW]
│   ├── __init__.py
│   ├── ollama.py          OllamaClient (port from ch8)
│   └── engine.py          retrieve → prompt → generate
│
├── web/                   [NEW]
│   ├── __init__.py        create_app() factory (FastAPI)
│   ├── api.py             JSON endpoints
│   ├── htmx.py            HTMX HTML fragments
│   └── templates/         Jinja2
│
└── exchange/              [keep stub for later — git-based hub]
```

## Schema decisions

### Keep convaix v1.0 unchanged

It's a public contract (advertised via `validate.py`'s
`schema_version == "1.0"` check). Do not bump until we hit a real blocker.

### Embedding dimension: 768 (nomic-embed-text-v1.5)

`nomic-embed-text-v1.5` exists as both a portable Hugging Face model
(via `sentence-transformers`) and an MLX-accelerated model. Same dim,
same vocabulary, same prefixes (`search_document:` / `search_query:`).
This means a Mac user gets the fast MLX path and a Linux/Windows user
gets the portable path — but the embeddings are interchangeable, so
the SQLite/PG schema is fixed.

If `sentence-transformers` ends up too heavy for desktop packaging, the
fallback is `nomic-embed-text-v1.5` via `llama.cpp` / `gguf` — same
weights, much smaller runtime.

Set `EMBEDDING_DIM = 768` once, in `embeddings/base.py`. Change later
only if a benchmark says we should.

### DB backend selection

A single `--db <url>` flag picks the backend:

- `sqlite:///path/to/convaix.db` → `sqlite_store`
- `postgresql://user:pw@host/db` → `pg_store`

Both implement the same `Store` ABC:

```python
class Store(Protocol):
    def init(self) -> None: ...
    def load_snapshot(self, conv_data: dict) -> bool: ...
    def chunk_snapshot(self, conv_data: dict, *, skip_embeddings: bool) -> int: ...
    def list_snapshots(self, *, source=None, author=None, limit=1000) -> list[Row]: ...
    def get_snapshot(self, convaix_id: str) -> Row | None: ...
    def get_snapshot_history(self, conv_id: str) -> list[Row]: ...
    def search_chunks(self, query: str, *, source=None, limit=10, mode="hybrid") -> list[Result]: ...
    def search_conversations(self, query: str, *, source=None, limit=20) -> list[Result]: ...
```

`search.py` becomes a thin shim that dispatches to whichever store is
active.

### Postgres tables (mirror of SQLite, names match convaix's)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE snapshots (
    convaix_id   TEXT PRIMARY KEY,
    conv_id      TEXT NOT NULL,
    title        TEXT NOT NULL,
    source       TEXT NOT NULL,
    source_id    TEXT,
    model        TEXT,
    created_at   TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    author       TEXT,
    tags         JSONB DEFAULT '[]',
    raw          JSONB NOT NULL,
    turn_count   INTEGER NOT NULL DEFAULT 0,
    total_chars  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ON snapshots (conv_id);
CREATE INDEX ON snapshots (author);
CREATE INDEX ON snapshots (source);

CREATE TABLE chunks (
    id           BIGSERIAL PRIMARY KEY,
    convaix_id   TEXT NOT NULL REFERENCES snapshots(convaix_id) ON DELETE CASCADE,
    turn_number  INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,
    role         TEXT NOT NULL,
    chunk_text   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding    vector(768),
    UNIQUE (convaix_id, turn_number, chunk_number)
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX ON chunks USING gin (chunk_text gin_trgm_ops);

-- discussions / discussion_refs / discussion_messages: same as SQLite
```

Note: PG keeps `embedding` *inline* on `chunks` (one less table); SQLite
needs the `chunks_vec` virtual table because sqlite-vec uses a vec0
virtual table. Both are fine.

## Provider contract

```python
# providers/base.py
class ProviderParser(Protocol):
    name: str  # "claude" | "chatgpt" | "gemini"

    def detect(self, path: str) -> bool:
        """Return True if path looks like an export from this provider."""

    def parse(self, path: str) -> Iterator[dict]:
        """Yield convaix v1.0 dicts (already passed through convert_to_schema)."""
```

CLI usage:

```
convaix import claude   ./Anthropic-export.json    --db <url>
convaix import chatgpt  ./conversations.json       --db <url>
convaix import gemini   ./Takeout/MyActivity.html  --db <url>
convaix import auto     ./some-file                --db <url>   # uses detect()
```

This keeps the existing `convaix load <dir-of-v1.0-json>` flow alive
(it's the canonical "schema-already-correct" path) and adds the
provider-aware front door.

## RAG orientation

Two separate things, both useful:

1. **Search over imports** — "find conversations where I discussed Lakehouse"
   → returns chunks + chip back to the source conversation. This is the
   *primary* feature.
2. **RAG chat using imports as the corpus** — "summarize my Claude
   conversations about embeddings" → retrieve → Ollama → answer with
   citations. This is the bonus feature; reuses ch8's `ConversationRAG`
   with `documents` swapped for `snapshots`.

Both are powered by the same `Store.search_chunks()` call.

## What we are explicitly NOT building yet

- The "social network" / public hub. Schema supports it (x-convaix.author,
  signature, parent_refs, discussion tables) but UI / federation /
  signing are post-demo.
- SaaS multi-tenant deployment. Per chat: explicitly out of scope.
- Authentication. Local app, single user, for now.
- Tauri / desktop packaging. Last milestone.
