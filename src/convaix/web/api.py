"""JSON API endpoints."""

import json
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _store(request: Request):
    return request.app.state.store


@router.get("/health")
def health(request: Request):
    from ..rag.ollama import OllamaClient
    ollama = OllamaClient()
    return {"status": "ok", "ollama": ollama.is_available()}


@router.get("/snapshots")
def list_snapshots(request: Request, source: str = None, limit: int = 100):
    return _store(request).list_snapshots(source=source, limit=limit)


@router.get("/snapshots/{convaix_id}")
def get_snapshot(convaix_id: str, request: Request):
    row = _store(request).get_snapshot(convaix_id)
    if not row:
        raise HTTPException(404, "Snapshot not found")
    data = json.loads(row["raw"]) if isinstance(row.get("raw"), str) else row.get("raw", {})
    return data


@router.get("/snapshots/{convaix_id}/turns")
def get_turns(convaix_id: str, request: Request):
    row = _store(request).get_snapshot(convaix_id)
    if not row:
        raise HTTPException(404)
    raw = json.loads(row["raw"]) if isinstance(row.get("raw"), str) else row.get("raw", {})
    return raw.get("turns", [])


@router.get("/search")
def search(request: Request, q: str, source: str = None, limit: int = 10, mode: str = "hybrid"):
    return _store(request).search_chunks(q, source=source, limit=limit, mode=mode)


@router.get("/search/conversations")
def search_convs(request: Request, q: str, source: str = None, limit: int = 20):
    return _store(request).search_conversations(q, source=source, limit=limit)


@router.get("/sources")
def list_sources(request: Request):
    rows = _store(request).list_snapshots(limit=10000)
    counts: dict = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    return [{"source": k, "count": v} for k, v in sorted(counts.items())]


@router.post("/ask")
def ask(request: Request, q: str, discussion_id: str = None, source: str = None):
    from ..rag.engine import RagEngine
    engine = RagEngine(_store(request))
    return engine.ask(q, discussion_id=discussion_id, source=source)


@router.post("/discussions")
def create_discussion(request: Request, title: str = "Chat", author: str = "user"):
    did = _store(request).create_discussion(title, author)
    return {"discussion_id": did}


@router.get("/discussions")
def list_discussions(request: Request, limit: int = 50):
    return _store(request).list_discussions(limit)


@router.get("/discussions/{discussion_id}")
def get_discussion(discussion_id: str, request: Request):
    msgs = _store(request).get_discussion_messages(discussion_id)
    return {"discussion_id": discussion_id, "messages": msgs}
