"""PostgreSQL + pgvector store."""

import hashlib
import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768

SCHEMA_SQL = f"""
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
CREATE INDEX IF NOT EXISTS idx_snap_conv_id ON snapshots(conv_id);
CREATE INDEX IF NOT EXISTS idx_snap_author  ON snapshots(author);
CREATE INDEX IF NOT EXISTS idx_snap_source  ON snapshots(source);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    convaix_id   TEXT NOT NULL REFERENCES snapshots(convaix_id) ON DELETE CASCADE,
    turn_number  INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,
    role         TEXT NOT NULL,
    chunk_text   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding    vector({EMBEDDING_DIM}),
    UNIQUE (convaix_id, turn_number, chunk_number)
);
CREATE INDEX IF NOT EXISTS idx_chunks_emb ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_chunks_trgm ON chunks
    USING GIN (chunk_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS discussions (
    discussion_id TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    created_by    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discussion_messages (
    id            BIGSERIAL PRIMARY KEY,
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    author        TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emb_to_pg(emb: list[float]) -> str:
    return "[" + ",".join(str(x) for x in emb) + "]"


class PgStore:
    def __init__(self, url: str):
        try:
            import psycopg
        except ImportError:
            raise ImportError("psycopg[binary] is required for Postgres: pip install 'psycopg[binary]'")
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        self._pool = ConnectionPool(url, min_size=2, max_size=10, open=True)
        self._dict_row = dict_row
        self.init()

    @contextmanager
    def _conn(self):
        with self._pool.connection() as conn:
            conn.row_factory = self._dict_row
            yield conn

    def init(self) -> None:
        with self._conn() as conn:
            conn.execute(SCHEMA_SQL)
        logger.debug("PgStore initialised")

    # ------------------------------------------------------------------ #

    def load_snapshot(self, conv_data: dict) -> bool:
        ext = conv_data.get("x-convaix", {})
        convaix_id = ext.get("convaix_id")
        if not convaix_id:
            return False
        conv = conv_data["conversation"]
        stats = conv_data.get("statistics", {})
        author = ext.get("author", {}).get("handle", "")
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO snapshots
                       (convaix_id, conv_id, title, source, source_id, model,
                        created_at, published_at, author, tags, raw, turn_count, total_chars)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        convaix_id,
                        conv.get("id", ""),
                        conv.get("title", "Untitled"),
                        conv.get("source", "unknown"),
                        conv.get("source_id"),
                        conv.get("model"),
                        conv.get("created_at"),
                        ext.get("published_at"),
                        author,
                        json.dumps(conv.get("tags", [])),
                        json.dumps(conv_data),
                        stats.get("turn_count", 0),
                        stats.get("total_chars", 0),
                    ),
                )
            return True
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                return False
            raise

    def chunk_snapshot(self, conv_data: dict, *, skip_embeddings: bool = False) -> int:
        from ..chunking import split_into_chunks

        ext = conv_data.get("x-convaix", {})
        convaix_id = ext.get("convaix_id")
        title = conv_data["conversation"].get("title", "")
        turns = conv_data.get("turns", [])

        chunk_rows = []
        for turn in turns:
            content = turn.get("content", "")
            role = turn.get("role", "user")
            turn_num = turn.get("turn_number", 0)
            for j, para in enumerate(split_into_chunks(content)):
                content_hash = hashlib.sha256(para.encode()).hexdigest()
                chunk_rows.append((convaix_id, turn_num, j + 1, role, para, content_hash))

        stored = 0
        with self._conn() as conn:
            for row in chunk_rows:
                try:
                    conn.execute(
                        "INSERT INTO chunks (convaix_id,turn_number,chunk_number,role,chunk_text,content_hash) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        row,
                    )
                    stored += 1
                except Exception:
                    pass

        if not skip_embeddings and stored > 0:
            self._embed_chunks(convaix_id, title, chunk_rows)

        return stored

    def _embed_chunks(self, convaix_id, title, chunk_rows):
        try:
            from ..embeddings import get_embedder
            embedder = get_embedder()
        except ImportError:
            return

        texts = [f"[{title}] {role}: {para}" for (_, tn, cn, role, para, _) in chunk_rows]
        embeddings = embedder.encode(texts)

        with self._conn() as conn:
            for (cx_id, tn, cn, _, _, _), emb in zip(chunk_rows, embeddings):
                conn.execute(
                    "UPDATE chunks SET embedding = %s::vector WHERE convaix_id=%s AND turn_number=%s AND chunk_number=%s",
                    (_emb_to_pg(emb), cx_id, tn, cn),
                )

    # ------------------------------------------------------------------ #

    def list_snapshots(self, *, source=None, author=None, limit=1000) -> list[dict]:
        q = "SELECT convaix_id, conv_id, title, source, author, published_at, turn_count FROM snapshots"
        params, conds = [], []
        if source:
            conds.append("source = %s"); params.append(source)
        if author:
            conds.append("author = %s"); params.append(author)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY published_at DESC LIMIT %s"
        params.append(limit)
        with self._conn() as conn:
            return list(conn.execute(q, params).fetchall())

    def get_snapshot(self, convaix_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM snapshots WHERE convaix_id = %s", (convaix_id,)).fetchone()
            return dict(row) if row else None

    def get_snapshot_history(self, conv_id: str) -> list[dict]:
        with self._conn() as conn:
            return list(conn.execute(
                "SELECT convaix_id, conv_id, title, source, author, published_at, turn_count "
                "FROM snapshots WHERE conv_id = %s ORDER BY published_at",
                (conv_id,),
            ).fetchall())

    def get_chunks(self, convaix_id: str) -> list[dict]:
        with self._conn() as conn:
            return list(conn.execute(
                "SELECT * FROM chunks WHERE convaix_id = %s ORDER BY turn_number, chunk_number",
                (convaix_id,),
            ).fetchall())

    # ------------------------------------------------------------------ #

    def search_chunks(self, query: str, *, source=None, limit=10, mode="hybrid") -> list[dict]:
        results = {}

        if mode in ("keyword", "hybrid"):
            for r in self._kw_search(query, source, limit):
                key = (r["convaix_id"], r["chunk_text"][:100])
                results[key] = {**r, "match_type": "kw"}

        if mode in ("semantic", "hybrid"):
            for r in self._vec_search(query, source, limit):
                key = (r["convaix_id"], r["chunk_text"][:100])
                if key in results:
                    results[key]["match_type"] = "both"
                    results[key]["similarity"] = max(results[key]["similarity"], r["similarity"])
                else:
                    results[key] = {**r, "match_type": "sem"}

        return sorted(results.values(), key=lambda r: r["similarity"], reverse=True)[:limit]

    def _kw_search(self, query, source, limit):
        sf = "AND s.source = %s" if source else ""
        params = [f"%{query}%", f"%{query}%"]
        if source:
            params.append(source)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT c.role, c.chunk_text, s.title, s.source, s.convaix_id, 1.0::float AS similarity
                    FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id
                    WHERE (c.chunk_text ILIKE %s OR s.title ILIKE %s) {sf}
                    LIMIT %s""",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def _vec_search(self, query, source, limit):
        try:
            from ..embeddings import get_embedder
            q_emb = get_embedder().encode_query(query)
        except Exception:
            return []

        emb_str = _emb_to_pg(q_emb)
        sf = "AND s.source = %s" if source else ""
        params = [emb_str, emb_str]
        if source:
            params.append(source)
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT c.role, c.chunk_text, s.title, s.source, s.convaix_id,
                           (1 - (c.embedding <=> %s::vector))::float AS similarity
                    FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id
                    WHERE c.embedding IS NOT NULL {sf}
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s""",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def search_conversations(self, query: str, *, source=None, limit=20) -> list[dict]:
        sf = "AND s.source = %s" if source else ""
        params = [f"%{query}%", f"%{query}%"]
        if source:
            params.append(source)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT s.title, s.source, s.convaix_id, COUNT(*) AS hits, s.turn_count
                    FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id
                    WHERE (c.chunk_text ILIKE %s OR s.title ILIKE %s) {sf}
                    GROUP BY s.convaix_id, s.title, s.source, s.turn_count
                    ORDER BY hits DESC LIMIT %s""",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #

    def create_discussion(self, title: str, author: str) -> str:
        did = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO discussions (discussion_id, title, created_at, created_by) VALUES (%s,%s,%s,%s)",
                (did, title, _now(), author),
            )
        return did

    def add_discussion_message(self, discussion_id: str, author: str, content: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "INSERT INTO discussion_messages (discussion_id, author, content, created_at) VALUES (%s,%s,%s,%s) RETURNING id",
                (discussion_id, author, content, _now()),
            ).fetchone()
        return row["id"]

    def list_discussions(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            return list(conn.execute(
                "SELECT discussion_id, title, created_at, created_by FROM discussions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall())

    def get_discussion_messages(self, discussion_id: str) -> list[dict]:
        with self._conn() as conn:
            return list(conn.execute(
                "SELECT id, author, content, created_at FROM discussion_messages WHERE discussion_id = %s ORDER BY created_at",
                (discussion_id,),
            ).fetchall())

    def close(self) -> None:
        self._pool.close()
