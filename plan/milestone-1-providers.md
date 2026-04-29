# M1 — Provider Parsers

Fill the empty `convaix/src/convaix/providers/` package. This is the most
important milestone — without it, nothing else has data to work with.

## Deliverables

1. `providers/base.py` — `ProviderParser` ABC + registry
2. `providers/claude.py` — Anthropic export parser
3. `providers/chatgpt.py` — OpenAI conversations.json parser (handles tree)
4. `providers/gemini.py` — Google Takeout parser (best-effort)
5. New CLI sub-command: `convaix import <provider> <path> [--db ...]`
6. Tests against fixtures from M0.5

## Tasks

### 1.1 — Provider ABC and registry

`providers/base.py`:

```python
from typing import Iterator, Protocol
from pathlib import Path

class ProviderParser(Protocol):
    name: str

    def detect(self, path: Path) -> bool: ...
    def parse(self, path: Path) -> Iterator[dict]: ...
```

`providers/__init__.py`:

```python
from .claude import ClaudeParser
from .chatgpt import ChatGPTParser
from .gemini import GeminiParser

PARSERS = {
    "claude":  ClaudeParser(),
    "chatgpt": ChatGPTParser(),
    "gemini":  GeminiParser(),
}

def get_parser(name: str) -> ProviderParser:
    if name not in PARSERS:
        raise ValueError(f"Unknown provider: {name}. Known: {list(PARSERS)}")
    return PARSERS[name]

def detect_parser(path: Path) -> ProviderParser | None:
    for p in PARSERS.values():
        if p.detect(path):
            return p
    return None
```

### 1.2 — Claude parser

Anthropic export is one JSON file. Top level is an array of conversations,
each with shape (verify against the real fixture):

```json
[
  {
    "uuid": "abc-123",
    "name": "Conversation title",
    "created_at": "2024-...",
    "updated_at": "2024-...",
    "chat_messages": [
      {
        "uuid": "...",
        "sender": "human" | "assistant",
        "text": "...",
        "content": [ {"type": "text", "text": "..."} ],   // newer exports
        "created_at": "..."
      }
    ]
  }
]
```

Implementation notes:
- Field is sometimes `text`, sometimes `content[].text` — handle both.
- `sender == "human"` → role `user`; `sender == "assistant"` → role `assistant`.
- Use `convert_to_schema(source="claude", source_id=uuid, title=name, turns=...)`.
- Drop into `add_convaix_extension(...)` with `author_handle` from the CLI.
- Capture untouched original `chat_messages` blob in
  `conversation.metadata["raw_provider"]` so we can re-parse later.

### 1.3 — ChatGPT parser (tree → linear)

OpenAI's `conversations.json` has each conversation as:

```json
{
  "title": "...",
  "create_time": 1700000000.123,
  "mapping": {
    "node-uuid": {
      "id": "...",
      "parent": "parent-uuid" | null,
      "children": ["child-uuid", ...],
      "message": {
        "id": "...",
        "author": { "role": "user" | "assistant" | "system" | "tool" },
        "content": { "content_type": "text", "parts": ["..."] },
        "create_time": ...
      }
    },
    ...
  }
}
```

This is a tree. To linearize:
1. Find the root: node with `parent == None` and a real message (skip
   system stubs if needed).
2. Walk down, picking the *current* leaf path. ChatGPT's UI keeps a
   `current_node` field — use it if present; otherwise pick the longest
   path or the one matching `update_time`.
3. Skip nodes where `message` is null (these are tree-shaping placeholders).
4. Skip role `tool` for v1.0 (or merge into assistant turn metadata) —
   v1.0 only allows `user|assistant|system`.

Capture branches in `metadata["x-chatgpt-branches"]` so we don't lose
information.

### 1.4 — Gemini parser (Takeout)

Google Takeout for Gemini ("My Activity") gives one of:
- `MyActivity.html` — semi-structured HTML
- `MyActivity.json` — list of activity entries (per-prompt, no conversation grouping)

Strategy:
1. Try JSON first. Each entry has `title`, `time`, `details`. Group entries
   that share an explicit conversation id if one exists; otherwise group by
   short time gaps within the same Gemini session.
2. Fall back to HTML if JSON not found. Use BeautifulSoup; each
   `<div class="content-cell ...">` is one prompt or one response.
3. If grouping is uncertain, emit one conversation per prompt+response pair.
   Mark `conversation.metadata["grouping_confidence"] = "low"`.

This parser is lossy by nature. Document the limitation in the README and
move on.

### 1.5 — CLI sub-command

Extend `cli.py`:

```python
@main.command("import")
@click.argument("provider")        # claude | chatgpt | gemini | auto
@click.argument("path")
@click.option("--db", default=DEFAULT_DB)
@click.option("--author", default=os.getenv("USER", "local"))
@click.option("--skip-embeddings", is_flag=True)
def import_cmd(provider, path, db, author, skip_embeddings):
    """Import conversations from a provider export file."""
    from .providers import get_parser, detect_parser
    parser = detect_parser(Path(path)) if provider == "auto" else get_parser(provider)
    ...
    for conv_data in parser.parse(Path(path)):
        validate_conversation(conv_data)
        if "x-convaix" not in conv_data:
            add_convaix_extension(conv_data, author_handle=author)
        if load_snapshot(conn, conv_data):
            chunk_snapshot(conn, conv_data, skip_embeddings=skip_embeddings)
            ...
```

Same load/skip/error counter UI as today's `load` command. Reuse the
`Table` rendering.

### 1.6 — Tests

For each provider, in `tests/test_providers_<name>.py`:
- Test `detect()` returns True on the fixture and False on the others.
- Test `parse()` yields at least one v1.0-shaped dict that passes
  `validate_conversation`.
- Test that running `parse → convert_to_schema` is idempotent
  (parsing twice produces same `conv_id`).

Add `tests/test_cli_import.py` smoke test for the CLI sub-command using
Click's `CliRunner` and a temp SQLite DB.

## Definition of done

- `convaix import claude   tests/fixtures/claude_sample.json   --db sqlite://...` works.
- `convaix import chatgpt  tests/fixtures/chatgpt_sample.json  --db sqlite://...` works.
- `convaix import gemini   tests/fixtures/gemini_sample.html   --db sqlite://...` works.
- `convaix import auto     <any of the above>                  --db sqlite://...` works.
- `convaix list` shows all imported snapshots with `source` populated.
- `convaix search` returns hits across all three providers.
- Provider tests are green, including a non-Apple machine.

## Risks / mitigations

- **Real exports differ from spec.** Use real fixtures from M0.5; don't
  hand-write JSON.
- **Single export file is huge.** ChatGPT exports for power users can be
  100s of MB. Stream-parse with `ijson` if size is a problem; for the demo
  loading 100 MB into memory is fine.
- **Re-imports.** `load_snapshot` already returns False on duplicate
  `convaix_id`. The `convaix_id` is a UUID, so re-imports will create new
  snapshots. Use `conv_id` (stable hash) to detect "same conversation,
  different snapshot" and decide whether to skip.
