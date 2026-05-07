"""SQLite + sqlite-vec store."""

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    convaix_id   TEXT PRIMARY KEY,
    conv_id      TEXT NOT NULL,
    title        TEXT NOT NULL,
    source       TEXT NOT NULL,
    source_id    TEXT,
    model        TEXT,
    created_at   TEXT,
    published_at TEXT,
    author       TEXT,
    tags         TEXT DEFAULT '[]',
    raw          TEXT NOT NULL,
    turn_count   INTEGER NOT NULL DEFAULT 0,
    total_chars  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_snap_conv_id ON snapshots(conv_id);
CREATE INDEX IF NOT EXISTS idx_snap_author  ON snapshots(author);
CREATE INDEX IF NOT EXISTS idx_snap_source  ON snapshots(source);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    convaix_id   TEXT NOT NULL REFERENCES snapshots(convaix_id) ON DELETE CASCADE,
    turn_number  INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,
    role         TEXT NOT NULL,
    chunk_text   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(convaix_id, turn_number, chunk_number)
);

CREATE TABLE IF NOT EXISTS discussions (
    discussion_id TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    created_by    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discussion_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT NOT NULL REFERENCES discussions(discussion_id),
    author        TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SqliteStore:
    def __init__(self, path: str | Path):
        self._path = str(path)
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._vec_loaded = False
        self.init()

    def init(self) -> None:
        self._conn.executescript(SCHEMA_SQL)
        try:
            import sqlite_vec
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(embedding float[768])"
            )
            self._vec_loaded = True
            logger.debug("sqlite-vec loaded")
        except Exception as e:
            logger.debug("sqlite-vec not available: %s (keyword search only)", e)
        self._conn.commit()

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
            self._conn.execute(
                """INSERT INTO snapshots
                   (convaix_id, conv_id, title, source, source_id, model,
                    created_at, published_at, author, tags, raw, turn_count, total_chars)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def chunk_snapshot(self, conv_data: dict, *, skip_embeddings: bool = False) -> int:
        from ..chunking import split_into_chunks

        ext = conv_data.get("x-convaix", {})
        convaix_id = ext.get("convaix_id")
        title = conv_data["conversation"].get("title", "")
        turns = conv_data.get("turns", [])

        chunk_data = []
        for turn in turns:
            content = turn.get("content", "")
            role = turn.get("role", "user")
            turn_num = turn.get("turn_number", 0)
            for j, para in enumerate(split_into_chunks(content)):
                content_hash = hashlib.sha256(para.encode()).hexdigest()
                chunk_data.append((convaix_id, turn_num, j + 1, role, para, content_hash))

        stored = 0
        for row in chunk_data:
            try:
                self._conn.execute(
                    "INSERT INTO chunks (convaix_id,turn_number,chunk_number,role,chunk_text,content_hash) VALUES (?,?,?,?,?,?)",
                    row,
                )
                stored += 1
            except sqlite3.IntegrityError:
                pass

        if not skip_embeddings and stored > 0 and self._vec_loaded:
            self._embed_chunks(convaix_id, title, chunk_data)

        self._conn.commit()
        return stored

    def _embed_chunks(self, convaix_id, title, chunk_data):
        try:
            from ..embeddings import get_embedder
            embedder = get_embedder()
        except ImportError:
            return

        texts, chunk_ids = [], []
        for cx_id, turn_num, chunk_num, role, para, _ in chunk_data:
            texts.append(f"[{title}] {role}: {para}")
            row = self._conn.execute(
                "SELECT id FROM chunks WHERE convaix_id=? AND turn_number=? AND chunk_number=?",
                (cx_id, turn_num, chunk_num),
            ).fetchone()
            if row:
                chunk_ids.append(row["id"])

        if not texts:
            return

        embeddings = embedder.encode(texts)
        for chunk_id, emb in zip(chunk_ids, embeddings):
            self._conn.execute(
                "INSERT OR REPLACE INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                (chunk_id, json.dumps(emb)),
            )

    # ------------------------------------------------------------------ #

    def get_source_counts(self) -> dict:
        rows = self._conn.execute(
            "SELECT source, COUNT(*) as cnt FROM snapshots GROUP BY source"
        ).fetchall()
        return {r["source"]: r["cnt"] for r in rows}

    def list_snapshots(self, *, source=None, author=None, limit=1000, offset=0) -> list[dict]:
        q = "SELECT convaix_id, conv_id, title, source, author, published_at, turn_count FROM snapshots"
        params, conds = [], []
        if source:
            conds.append("source = ?")
            params.append(source)
        if author:
            conds.append("author = ?")
            params.append(author)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def get_snapshot(self, convaix_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE convaix_id = ?", (convaix_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_snapshot_history(self, conv_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT convaix_id, conv_id, title, source, author, published_at, turn_count "
            "FROM snapshots WHERE conv_id = ? ORDER BY published_at",
            (conv_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_chunks(self, convaix_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE convaix_id = ? ORDER BY turn_number, chunk_number",
            (convaix_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #

    def search_chunks(self, query: str, *, source=None, limit=10, mode="hybrid") -> list[dict]:
        results = {}

        if mode in ("keyword", "hybrid"):
            for r in self._kw_search(query, source, limit):
                key = (r["convaix_id"], r["chunk_text"][:100])
                results[key] = {**r, "match_type": "kw"}

        if mode in ("semantic", "hybrid") and self._vec_loaded:
            for r in self._vec_search(query, source, limit):
                key = (r["convaix_id"], r["chunk_text"][:100])
                if key in results:
                    results[key]["match_type"] = "both"
                    results[key]["similarity"] = max(results[key]["similarity"], r["similarity"])
                else:
                    results[key] = {**r, "match_type": "sem"}

        return sorted(results.values(), key=lambda r: r["similarity"], reverse=True)[:limit]

    def _kw_search(self, query, source, limit):
        pat = f"%{query}%"
        params = [pat, pat]
        sf = ""
        if source:
            sf = "AND s.source = ?"
            params.append(source)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT c.role, c.chunk_text, s.title, s.source, s.convaix_id, 1.0 AS similarity
                FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id
                WHERE (c.chunk_text LIKE ? OR s.title LIKE ?) {sf} LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def _vec_search(self, query, source, limit):
        try:
            from ..embeddings import get_embedder
            q_emb = get_embedder().encode_query(query)
        except Exception:
            return []

        rows = self._conn.execute(
            "SELECT v.rowid, v.distance FROM chunks_vec v WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (json.dumps(q_emb), limit),
        ).fetchall()

        results = []
        for row in rows:
            chunk = self._conn.execute(
                "SELECT c.role, c.chunk_text, c.convaix_id, s.title, s.source "
                "FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id WHERE c.id = ?",
                (row["rowid"],),
            ).fetchone()
            if chunk:
                results.append({**dict(chunk), "similarity": 1.0 - row["distance"]})
        return results

    def search_conversations(self, query: str, *, source=None, limit=20) -> list[dict]:
        pat = f"%{query}%"
        params = [pat, pat]
        sf = ""
        if source:
            sf = "AND s.source = ?"
            params.append(source)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT s.title, s.source, s.convaix_id, COUNT(*) AS hits, s.turn_count
                FROM chunks c JOIN snapshots s ON c.convaix_id = s.convaix_id
                WHERE (c.chunk_text LIKE ? OR s.title LIKE ?) {sf}
                GROUP BY s.convaix_id ORDER BY hits DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #

    def create_discussion(self, title: str, author: str) -> str:
        did = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO discussions (discussion_id, title, created_at, created_by) VALUES (?,?,?,?)",
            (did, title, _now(), author),
        )
        self._conn.commit()
        return did

    def add_discussion_message(self, discussion_id: str, author: str, content: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO discussion_messages (discussion_id, author, content, created_at) VALUES (?,?,?,?)",
            (discussion_id, author, content, _now()),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_discussions(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT discussion_id, title, created_at, created_by FROM discussions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_discussion_messages(self, discussion_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, author, content, created_at FROM discussion_messages WHERE discussion_id = ? ORDER BY created_at",
            (discussion_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
