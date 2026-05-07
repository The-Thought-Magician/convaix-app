"""HTMX HTML fragment endpoints."""

import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

SOURCE_BADGES = {
    "claude":  ("#cc785c", "Claude"),
    "chatgpt": ("#74aa9c", "ChatGPT"),
    "gemini":  ("#4285f4", "Gemini"),
}


def _badge(source: str) -> str:
    color, label = SOURCE_BADGES.get(source, ("#888", source))
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:0.8em">{label}</span>'


def _store(request: Request):
    return request.app.state.store


@router.get("/", response_class=HTMLResponse)
def index(request: Request, source: str = None, page: int = 1):
    store = _store(request)
    limit = 50
    snapshots = store.list_snapshots(source=source, limit=limit)
    sources = store.list_snapshots(limit=10000)
    source_counts: dict = {}
    for r in sources:
        source_counts[r["source"]] = source_counts.get(r["source"], 0) + 1

    rows_html = ""
    for s in snapshots:
        badge = _badge(s["source"])
        rows_html += f"""
        <tr>
          <td>{badge}</td>
          <td><a href="/htmx/conv/{s['convaix_id']}">{s['title']}</a></td>
          <td>{s.get('turn_count', 0)}</td>
          <td style="color:#888;font-size:0.85em">{(s.get('published_at') or '')[:10]}</td>
        </tr>"""

    sidebar = '<ul style="list-style:none;padding:0">'
    sidebar += '<li><a href="/htmx/">All</a></li>'
    for src, cnt in sorted(source_counts.items()):
        color, label = SOURCE_BADGES.get(src, ("#888", src))
        sidebar += f'<li><a href="/htmx/?source={src}" style="color:{color}">{label} ({cnt})</a></li>'
    sidebar += "</ul>"

    return HTMLResponse(_layout(f"""
    <div style="display:flex;gap:24px">
      <aside style="width:160px;flex-shrink:0">{sidebar}</aside>
      <main style="flex:1">
        <form method="get" action="/htmx/search" style="margin-bottom:16px">
          <input name="q" placeholder="Search conversations…" style="width:70%;padding:8px">
          <button type="submit">Search</button>
        </form>
        <table style="width:100%;border-collapse:collapse">
          <thead><tr>
            <th style="text-align:left;padding:6px">Source</th>
            <th style="text-align:left;padding:6px">Title</th>
            <th style="text-align:left;padding:6px">Turns</th>
            <th style="text-align:left;padding:6px">Date</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </main>
    </div>
    """, title="convaix — your conversations"))


@router.get("/conv/{convaix_id}", response_class=HTMLResponse)
def conversation(convaix_id: str, request: Request):
    store = _store(request)
    row = store.get_snapshot(convaix_id)
    if not row:
        return HTMLResponse("<p>Not found</p>", status_code=404)

    raw = json.loads(row["raw"]) if isinstance(row.get("raw"), str) else row.get("raw", {})
    conv = raw.get("conversation", {})
    turns = raw.get("turns", [])
    badge = _badge(conv.get("source", "unknown"))
    model = conv.get("model") or ""

    turns_html = ""
    for t in turns:
        role = t.get("role", "user")
        content = t.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
        content = content.replace("\n", "<br>")
        bg = "#e3f2fd" if role == "user" else "#f5f5f5"
        turns_html += f"""
        <div id="turn-{t.get('turn_number', '')}" style="background:{bg};padding:12px;margin:8px 0;border-radius:8px">
          <strong style="text-transform:capitalize">{role}</strong>
          <p style="margin:8px 0 0">{content}</p>
        </div>"""

    return HTMLResponse(_layout(f"""
    <p><a href="/htmx/">← Back</a></p>
    <h2>{conv.get('title', 'Untitled')} {badge}</h2>
    <p style="color:#888;font-size:0.9em">Model: {model} &nbsp;|&nbsp; {len(turns)} turns</p>
    <div>{turns_html}</div>
    """, title=conv.get("title", "Conversation")))


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    if not q.strip():
        return HTMLResponse(_layout("<p>Enter a query above.</p>", title="Search"))

    store = _store(request)
    convs = store.search_conversations(q, limit=10)
    chunks = store.search_chunks(q, limit=10)

    convs_html = ""
    for c in convs:
        badge = _badge(c["source"])
        convs_html += f'<li>{badge} <a href="/htmx/conv/{c["convaix_id"]}">{c["title"]}</a> — {c["hits"]} hits</li>'

    chunks_html = ""
    for c in chunks:
        badge = _badge(c["source"])
        snippet = c["chunk_text"][:200].replace("<", "&lt;")
        chunks_html += f"""
        <div style="border:1px solid #ddd;padding:10px;margin:6px 0;border-radius:6px">
          {badge} <a href="/htmx/conv/{c['convaix_id']}">{c['title']}</a>
          <p style="color:#555;font-size:0.9em;margin:4px 0">{snippet}…</p>
        </div>"""

    return HTMLResponse(_layout(f"""
    <p><a href="/htmx/">← Back</a></p>
    <h2>Search: "{q}"</h2>
    <h3>Conversations</h3><ul>{convs_html or "<li>No results</li>"}</ul>
    <h3>Matching excerpts</h3>{chunks_html or "<p>No results</p>"}
    <hr>
    <h3>Ask a question</h3>
    <form hx-post="/htmx/ask" hx-target="#answer" hx-swap="innerHTML">
      <input type="hidden" name="q" value="{q}">
      <button type="submit">Ask Ollama about these results</button>
    </form>
    <div id="answer"></div>
    """, title=f'Search: {q}'))


@router.post("/ask", response_class=HTMLResponse)
async def ask_htmx(request: Request):
    form = await request.form()
    q = form.get("q", "")
    discussion_id = form.get("discussion_id") or None
    source = form.get("source") or None

    if not q.strip():
        return HTMLResponse("<p>Empty query.</p>")

    from ..rag.engine import RagEngine
    engine = RagEngine(_store(request))
    result = engine.ask(q, discussion_id=discussion_id, source=source)

    sources_html = ""
    for i, s in enumerate(result["sources"], 1):
        badge = _badge(s["source"])
        sources_html += f'<li>{badge} <a href="/htmx/conv/{s["convaix_id"]}">{s["title"]}</a> [{s["match_type"]}] {s["similarity"]:.3f}</li>'

    answer_text = result["answer"].replace("<", "&lt;").replace("\n", "<br>")
    return HTMLResponse(f"""
    <div style="background:#f5f5f5;padding:12px;border-radius:8px;margin:8px 0">
      <strong>Answer</strong>
      <p>{answer_text}</p>
      <details><summary style="cursor:pointer;color:#666">Sources ({len(result['sources'])})</summary>
        <ul>{sources_html}</ul>
      </details>
      <small style="color:#999">{result['total_ms']}ms total</small>
    </div>
    """)


def _layout(body: str, title: str = "convaix") -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; }}
    a {{ color: #1976d2; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    button {{ padding: 8px 16px; background: #1976d2; color: #fff; border: none; border-radius: 4px; cursor: pointer; }}
    table th, table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
  </style>
</head>
<body>
  <header style="border-bottom:2px solid #1976d2;margin-bottom:16px;padding-bottom:8px">
    <a href="/htmx/" style="font-size:1.4em;font-weight:700;color:#1976d2">convaix</a>
    <span style="color:#888;margin-left:8px">your AI conversations, unified</span>
  </header>
  {body}
</body>
</html>"""
