# M2 — Postgres Backend

Mirror the SQLite store as a `pgvector` store, behind the same `Store` ABC.
Per Nitin's chat: "first make it work on Pg then on SQLite3" — but SQLite
already works, so we are *adding* PG, not replacing.

## Deliverables

1. `convaix/db/base.py` — `Store` ABC
2. `convaix/db/sqlite_store.py` — moved from `db.py`
3. `convaix/db/pg_store.py` — new
4. `convaix/db/__init__.py` — `get_store(url)` factory
5. `search.py` made store-agnostic (drop direct `conn.execute` calls)
6. CLI `--db` flag accepts `sqlite://` and `postgresql://` URLs
7. Tests: same snapshot fixtures pass against both stores

## Tasks

### 2.1 — Store ABC

`convaix/db/base.py`:

```python
from typing import Protocol, runtime_checkable
from contextlib import AbstractContextManager

@runtime_checkable
class Store(Protocol):
    def init(self) -> None: ...

    def load_snapshot(self, conv_data: dict) -> bool: ...
    def chunk_snapshot(self, conv_data: dict, *, skip_embeddings: bool = False) -> int: ...

    def list_snapshots(self, *, source: str | None = None,
                       author: str | None = None,
                       limit: int = 1000) -> list[dict]: ...

    def get_snapshot(self, convaix_id: str) -> dict | None: ...
    def get_snapshot_history(self, conv_id: str) -> list[dict]: ...
    def get_chunks(self, convaix_id: str) -> list[dict]: ...

    def search_chunks(self, query: str, *,
                      source: str | None = None,
                      limit: int = 10,
                      mode: str = "hybrid") -> list[dict]: ...

    def search_conversations(self, query: str, *,
                             source: str | None = None,
                             limit: int = 20) -> list[dict]: ...

    def close(self) -> None: ...
```

Use plain dicts in / out — keeps SQLite and PG row formats compatible at the
boundary (both can return dict-like objects today).

### 2.2 — Move SQLite code into `sqlite_store.py`

Copy the bulk of today's `db.py` into `db/sqlite_store.py` and wrap as
`SqliteStore(Store)`. Keep `init_db`, `load_snapshot`, etc. as module-level
functions or class methods — either works. Important: do not change the
SQL or the schema. This step is purely structural.

After this commit, run the existing test suite — should still pass.

### 2.3 — `pg_store.py`

```python
import os, json, logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager

EMBEDDING_DIM = 768

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS snapshots (
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
CREATE INDEX IF NOT EXISTS idx_snapshots_conv_id ON snapshots(conv_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_author  ON snapshots(author);
CREATE INDEX IF NOT EXISTS idx_snapshots_source  ON snapshots(source);

CREATE TABLE IF NOT EXISTS chunks (
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
CREATE INDEX IF NOT EXISTS idx_chunks_emb ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_chunks_text_trgm ON chunks
    USING GIN (chunk_text gin_trgm_ops);

-- discussions / discussion_refs / discussion_messages: same as SQLite (TEXT FKs are fine)
"""


class PgStore:
    def __init__(self, url: str):
        self._pool = pool.ThreadedConnectionPool(2, 10, dsn=url)
        self.init()

    @contextmanager
    def _conn(self):
        c = self._pool.getconn()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            self._pool.putconn(c)

    def init(self):
        with self._conn() as c, c.cursor() as cur:
            cur.execute(SCHEMA_SQL)
    ...
```

Implementation parity points to watch:

| Concern | SQLite | Postgres |
| --- | --- | --- |
| `embedding` storage | `chunks_vec` virtual table (rowid-aligned) | `embedding vector(768)` column on `chunks` |
| Hybrid search (kw side) | `LIKE %q%` on `chunk_text` | `to_tsvector('english', chunk_text) @@ plainto_tsquery(q)` + `ts_rank_cd` |
| Hybrid search (vec side) | `WHERE embedding MATCH ?` (sqlite-vec) | `ORDER BY embedding <=> %s::vector` |
| JSON fields | `TEXT` blobs, `json.loads` on read | `JSONB` columns, native dicts |

The Store ABC hides this; callers just see `list[dict]`.

### 2.4 — Embedding parity

`embeddings/sentence_tf.py` uses
`sentence-transformers` with `nomic-ai/nomic-embed-text-v1.5`. Both
`embed_texts(texts)` and `embed_query(text)` must return 768-dim
`list[float]` matching what MLX would return. Verify with a small
ground-truth fixture in `tests/test_embeddings_parity.py`.

`embeddings/__init__.py`:

```python
def get_embedder(prefer: str = "auto"):
    """Return an embedder. prefer: 'mlx' | 'sentence_tf' | 'auto'."""
    if prefer in ("mlx", "auto"):
        try:
            from .mlx_nomic import MlxNomic
            return MlxNomic()
        except ImportError:
            if prefer == "mlx":
                raise
    from .sentence_tf import SentenceTfNomic
    return SentenceTfNomic()
```

Always 768-dim. Always nomic. Either backend is interchangeable.

### 2.5 — `get_store(url)` factory

`convaix/db/__init__.py`:

```python
def get_store(url: str | None = None):
    url = url or os.getenv("CONVAIX_DB", f"sqlite://{DEFAULT_SQLITE_PATH}")
    if url.startswith("sqlite://"):
        from .sqlite_store import SqliteStore
        return SqliteStore(url.removeprefix("sqlite://"))
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        from .pg_store import PgStore
        return PgStore(url)
    raise ValueError(f"Unsupported DB url: {url}")
```

### 2.6 — Wire CLI through the factory

Replace direct `init_db(db)` calls in `cli.py` with `get_store(db_url)`.
Existing `--db <path>` still works because we coerce a bare path into
`sqlite://` if the URL has no scheme.

### 2.7 — Cross-store tests

`tests/conftest.py`:

```python
@pytest.fixture(params=["sqlite", "pg"])
def store(request, tmp_path):
    if request.param == "sqlite":
        yield get_store(f"sqlite://{tmp_path}/test.db")
    else:
        if not os.getenv("CONVAIX_TEST_PG_URL"):
            pytest.skip("CONVAIX_TEST_PG_URL not set")
        yield get_store(os.environ["CONVAIX_TEST_PG_URL"])
```

Then run the same load/search assertions against both.

### 2.8 — Bench (optional but cheap)

Quick `bench/` script: load 100 / 1000 conversations into each backend,
time `search_chunks("foo")`. Helps justify which backend defaults for the
desktop bundle.

## Definition of done

- `convaix import claude … --db postgresql://…` works.
- `convaix search "X" --db postgresql://…` returns hits.
- Same fixture data produces equivalent results on both backends.
- `pytest` parametrized over both stores is green when PG URL is set;
  green skipping PG when not.

## Risks / mitigations

- **psycopg2 vs psycopg3.** Use `psycopg[binary]` (psycopg3) — better
  ergonomics, modern. Alternatively stick with `psycopg2-binary` since
  ch8 uses it. Pick one in M2.1; don't mix.
- **Different ranking between backends.** Hybrid scoring weights will
  produce slightly different orderings. Document this and leave tunable
  via `CONVAIX_SEMANTIC_WEIGHT` env var (default 0.7).
- **HNSW build time on big datasets.** Defer index creation in tests with
  `SET maintenance_work_mem = '256MB';` if needed.
