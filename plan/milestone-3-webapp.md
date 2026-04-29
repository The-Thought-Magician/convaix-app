# M3 — Web UI on convaix Schema

Port ch8's FastAPI + HTMX shell into `convaix/web/`, but rewire it to
operate over `snapshots`/`chunks` instead of `documents`/`document_chunks`.

End state: `convaix serve` starts a local web app where the user can
browse imported conversations and search across them.

## Deliverables

1. `convaix/web/__init__.py` exposing `create_app(store)` (FastAPI factory)
2. `convaix/web/api.py` — JSON endpoints
3. `convaix/web/htmx.py` — HTML fragment endpoints
4. `convaix/web/templates/` — Jinja2 (index, conversation, search results)
5. `convaix/web/static/` — minimal CSS, htmx.js (CDN OK for now)
6. New CLI: `convaix serve [--db ...] [--port 8000]`

## Tasks

### 3.1 — App factory + DI

```python
# convaix/web/__init__.py
from fastapi import FastAPI
from ..db import get_store

def create_app(db_url: str | None = None) -> FastAPI:
    app = FastAPI(title="convaix", version="0.1.0")
    store = get_store(db_url)
    app.state.store = store
    from .api import router as api_router
    from .htmx import router as htmx_router
    app.include_router(api_router, prefix="/api")
    app.include_router(htmx_router, prefix="/htmx")
    @app.get("/")
    def index():
        return RedirectResponse("/htmx/")
    return app
```

### 3.2 — JSON endpoints (`api.py`)

| Method + path | Returns |
| --- | --- |
| `GET  /api/health` | `{"status": "ok", "store": "pg"\|"sqlite", "embedder": "mlx"\|"st"}` |
| `GET  /api/snapshots?source=&author=&limit=` | List rows |
| `GET  /api/snapshots/{convaix_id}` | Full snapshot (raw JSON) |
| `GET  /api/snapshots/{convaix_id}/turns` | Just turns (paginated) |
| `GET  /api/conv/{conv_id}/history` | All snapshots in lineage |
| `GET  /api/search?q=&source=&limit=&mode=hybrid|kw|sem` | Chunk hits |
| `GET  /api/search/conversations?q=&source=&limit=` | Conversation hits |
| `GET  /api/sources` | Distinct source names + counts |

All endpoints take `app.state.store` and return JSON. No business logic
here — just thin marshalling.

### 3.3 — HTMX endpoints (`htmx.py`)

Server-rendered Jinja partials. Three pages:

- `GET /htmx/` — landing. Sidebar with sources + counts; main pane lists
  snapshots, paginated. Search input at top.
- `GET /htmx/conv/{convaix_id}` — full conversation view: title, model,
  source badge, then turns rendered as user/assistant bubbles. Markdown
  rendered (use `markdown-it-py`).
- `GET /htmx/search?q=...` — combined results: top conversations by hit
  count + top chunks. Each hit links into `/htmx/conv/{convaix_id}#turn-N`.

Reuse ch8's CSS skeleton — copy `<style>` block from `ch8/app.py`'s
`index()` route as the starting point.

### 3.4 — Sidebar / source badges

Each conversation gets a coloured pill: `claude` / `chatgpt` / `gemini`.
`source` field in the schema drives this. Use a small dictionary in the
template:

```python
SOURCE_BADGES = {
    "claude":  ("Claude",  "#cc785c"),
    "chatgpt": ("ChatGPT", "#74aa9c"),
    "gemini":  ("Gemini",  "#4285f4"),
}
```

### 3.5 — Drag-and-drop import (stretch)

If time allows: a "+ Import" button on the landing page that opens a file
chooser → posts to `POST /htmx/import` with provider auto-detection. The
backend runs the same logic as `convaix import auto`. Renders a progress
fragment using HTMX SSE or a simple polling endpoint. Skip if time is
short — CLI import is fine for the demo.

### 3.6 — CLI

```python
@main.command()
@click.option("--db", default=None)
@click.option("--port", default=8000)
@click.option("--host", default="127.0.0.1")
def serve(db, port, host):
    """Run the convaix web app."""
    import uvicorn
    from .web import create_app
    app = create_app(db)
    uvicorn.run(app, host=host, port=port)
```

### 3.7 — Tests

`tests/test_web.py` using `httpx.AsyncClient`:

- `GET /api/health` returns 200
- Import a fixture, then `GET /api/snapshots` returns it
- `GET /api/search?q=...` returns hits
- `GET /htmx/` returns HTML containing the snapshot title

## Definition of done

- `convaix serve` opens a working web app at `http://127.0.0.1:8000/`.
- Landing page lists imported conversations with source badges.
- Clicking a conversation shows the full thread.
- Search box returns ranked hits across all imported sources.
- Works against both SQLite and Postgres without code change.

## Demo script (rehearsal)

1. `docker compose up -d`
2. `convaix import claude   ~/exports/claude.json   --db postgresql://...`
3. `convaix import chatgpt  ~/exports/chatgpt.json  --db postgresql://...`
4. `convaix import gemini   ~/exports/gemini.html   --db postgresql://...`
5. `convaix serve --db postgresql://...`
6. Open browser. Show unified list. Search for a topic that came up in
   multiple LLM chats. Click a result. Done.

## Risks / mitigations

- **Markdown rendering of LLM output.** Real conversations have code
  blocks, tables, math. `markdown-it-py` + `pygments` for syntax
  highlighting handles 95%. Math (KaTeX) is optional for the demo.
- **Pagination.** A heavy user has 1000+ ChatGPT conversations. Default
  `LIMIT 50`, infinite scroll or "Load more" button. Don't try to render
  everything.
- **HTMX vs SPA.** Stick with HTMX. ch8 already uses it; lower risk;
  faster to build; ships smaller in the desktop bundle.
