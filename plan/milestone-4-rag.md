# M4 — RAG over Imports

Reuse ch8's `OllamaClient` + `ConversationRAG` flow to let the user
ask questions across their imported conversations. The vector store
is already in place from M2; this milestone is mostly prompt + UI work.

## Deliverables

1. `convaix/rag/ollama.py` — port from ch8 (no changes other than imports)
2. `convaix/rag/engine.py` — `RagEngine.ask(query, ...)` using `Store.search_chunks`
3. New API endpoints: `POST /api/ask`, `POST /htmx/ask`
4. New chat panel in the web UI
5. CLI: `convaix ask "<question>" [--db ...]` for headless use

## Tasks

### 4.1 — Port `OllamaClient`

Copy `OllamaClient` from `ch8/app.py` lines ~497-564 into
`convaix/rag/ollama.py`. No logic changes. Drop hardcoded model name
into `OLLAMA_MODEL` env var with a sensible default
(`llama3.1:8b` or `qwen2.5:14b`).

### 4.2 — `RagEngine`

```python
class RagEngine:
    def __init__(self, store, ollama=None, embedder=None):
        self.store = store
        self.ollama = ollama or OllamaClient()
        self.embedder = embedder or get_embedder()

    def ask(self, query: str, *, num_chunks: int = 5,
            source: str | None = None) -> dict:
        chunks = self.store.search_chunks(
            query, source=source, limit=num_chunks, mode="hybrid"
        )
        prompt = self._build_prompt(query, chunks)
        answer = self.ollama.generate(prompt)
        return {
            "answer": answer,
            "sources": [
                {
                    "convaix_id": c["convaix_id"],
                    "title": c["title"],
                    "source": c["source"],
                    "role": c["role"],
                    "snippet": c["chunk_text"][:300],
                    "similarity": c["similarity"],
                }
                for c in chunks
            ],
        }

    def _build_prompt(self, q, chunks): ...   # adapt from ch8 _build_prompt
```

The prompt template can lift directly from ch8 — just rename "documents"
→ "conversations" and "Source N" → cite by convaix_id.

### 4.3 — Chat session storage

Use the existing `discussions` / `discussion_messages` tables that
already live in `convaix/db.py`. They were added for the social-network
idea but work fine as a "chat with your corpus" history.

Add `Store.create_discussion(title, author)`, `Store.add_message(...)`,
`Store.list_discussions()`, `Store.get_discussion(id)` — same shape on
both backends.

### 4.4 — Web endpoints

| Method + path | Body | Returns |
| --- | --- | --- |
| `POST /api/ask` | `{question, discussion_id?, source?}` | `{answer, sources, discussion_id, latency_ms}` |
| `GET  /api/discussions` | — | list |
| `GET  /api/discussions/{id}` | — | full thread |
| `POST /htmx/ask` | form-encoded | HTML fragment |

HTMX flow: a chat panel on a third route `/htmx/chat[/id]`. Form
submission appends `<div class="message user">…</div>` then
`<div class="message assistant">…<div class="sources">…</div></div>`.

### 4.5 — Citation chips

Each source rendered as a chip linking to
`/htmx/conv/{convaix_id}#turn-{turn_number}` so the user can click
through to the original conversation. This is the killer feature —
it closes the loop between "find me a thing" and "show me where I
discussed it".

### 4.6 — Source filter

Optional dropdown on the chat panel: "Search across [all | claude |
chatgpt | gemini]". Wires through the `source` parameter.

### 4.7 — CLI

```python
@main.command()
@click.argument("question")
@click.option("--db", default=None)
@click.option("--source", default=None)
@click.option("--num-chunks", default=5)
def ask(question, db, source, num_chunks):
    """Ask a question against your imported corpus."""
    engine = RagEngine(get_store(db))
    result = engine.ask(question, num_chunks=num_chunks, source=source)
    console.print(result["answer"])
    table = Table(title="Sources")
    for s in result["sources"]:
        table.add_row(s["source"], s["title"], f"{s['similarity']:.3f}")
    console.print(table)
```

### 4.8 — Tests

- `tests/test_rag.py`: unit-test `_build_prompt` with mocked store.
- Skip the live-Ollama path under `pytest -m "not slow"`.
- Smoke test: stub `OllamaClient.generate` and verify the engine wires
  store → prompt → answer correctly.

## Definition of done

- `convaix ask "what did I discuss about X?"` returns an answer with
  citations.
- Web `/htmx/chat` page works, citations link back to conversations.
- Filtering by source works.
- Discussion history persists across server restarts.

## Risks / mitigations

- **Ollama not installed on the user's machine.** Fall back to OpenAI /
  Anthropic API calls with an API key. Make this an opt-in env var
  (`CONVAIX_LLM=openai:gpt-4o-mini`) so the desktop bundle still works
  without local LLM weights. Bundle Ollama separately or document
  install instructions.
- **Hallucinated citations.** The retrieved chunks are real, but the
  LLM can still misattribute. Mitigate with explicit prompt instruction:
  "Cite using [source N]; if you're unsure, say so." Already in ch8's
  prompt; keep it.
- **Long conversations blow context window.** Cap `num_chunks * chunk_chars`
  to `~6000` tokens. Truncate per-chunk if needed.
