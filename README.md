# convaix

[![CI](https://github.com/chiranjeetmishra/convaix/actions/workflows/ci.yml/badge.svg)](https://github.com/chiranjeetmishra/convaix/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**Your AI conversations, unified.** Import conversations from Claude, ChatGPT, and Gemini into a single searchable corpus with semantic search and RAG.

## Overview

convaix is an open-source conversation management system that:
- **Imports** conversations from Claude, ChatGPT, and Gemini with auto-detection
- **Stores** them in a unified schema (convaix v1.0) with vector embeddings
- **Searches** across all conversations with hybrid semantic + keyword search
- **Retrieves** relevant context for RAG (Retrieval-Augmented Generation) with Ollama
- **Serves** a web UI for browsing, searching, and asking questions

### Use Cases
- **Knowledge base** — search your conversation history across all AI platforms
- **Research** — organize and find relevant discussions across months of conversations
- **RAG applications** — ground LLM responses in your actual AI conversation data
- **Analysis** — understand patterns in how you interact with different AI models

## Features

✨ **Multi-Provider Support**
- Claude (Anthropic) — full export JSON support
- ChatGPT (OpenAI) — tree-shaped `mapping` exports, linearized to flat list
- Gemini (Google) — Takeout entries, grouped by 30-min session gaps

🔍 **Hybrid Search**
- **Semantic search** — find conversations by meaning using 768-dim embeddings (nomic-embed-text-v1.5)
- **Keyword search** — full-text search with trigram similarity
- **Combined** — automatic relevance ranking across both modes

📦 **Database Options**
- **SQLite** (default) — embedded, zero-config, perfect for local-first apps
  - sqlite-vec for fast vector search (optional)
- **PostgreSQL** — production-ready, HNSW indexes, concurrent access
  - pgvector for vector operations

🌐 **Web UI**
- FastAPI backend + HTMX frontend (server-rendered, no SPA overhead)
- Conversation browser with source filtering
- Real-time search with similarity scores
- RAG integration for asking questions

💬 **RAG Integration**
- Uses Ollama for local LLM inference (no external APIs)
- Retrieves top-k relevant chunks from corpus
- Formats context and generates responses
- Tracks sources and similarity scores

🧪 **Developer Experience**
- 18 comprehensive tests (all passing)
- Full type checking with ruff
- Clean separation of concerns (providers, db, embeddings, web)
- Extensible provider interface for adding new sources

## Installation

### Requirements
- Python 3.10+
- (Optional) PostgreSQL with pgvector extension for production
- (Optional) Ollama for RAG features

### Quick Start

```bash
# Clone and enter directory
git clone <repo>
cd convaix-app

# Create virtual environment with uv
uv sync --extra web --extra embeddings

# Activate environment
source .venv/bin/activate

# Import conversations
convaix import claude /path/to/claude_export.json
convaix import chatgpt /path/to/chatgpt_export.json
convaix import gemini /path/to/gemini_export.json

# Start web UI
convaix serve
# Visit http://localhost:8000
```

### Install with All Features

```bash
# Install with PostgreSQL support + RAG
uv sync --extra web --extra pg --extra rag --extra embeddings

# Or specify database when running
convaix serve --db postgresql://user:pass@localhost/convaix
```

## Usage

### CLI Commands

#### Import conversations
```bash
# Auto-detect provider
convaix import auto /path/to/export.json

# Explicit provider
convaix import claude /path/to/export.json
convaix import chatgpt /path/to/export.json
convaix import gemini /path/to/export.json

# Custom database location
convaix import claude export.json --db sqlite:///home/user/.convaix/db.sqlite

# Skip embeddings (faster, keyword-only search)
convaix import claude export.json --skip-embeddings

# Set author/attribution
convaix import claude export.json --author "my-handle"
```

#### List conversations
```bash
convaix list

# Filter by source
convaix list --source claude

# Limit results
convaix list --limit 50
```

#### Search conversations
```bash
# Hybrid search (default: semantic + keyword)
convaix search "how do embeddings work?"

# Keyword only
convaix search "vector database" --mode keyword

# Semantic only (requires embeddings)
convaix search "RAG applications" --mode semantic

# Filter by source and limit
convaix search "embeddings" --source claude --limit 20
```

#### Ask questions (requires Ollama)
```bash
# Ask based on corpus
convaix ask "What are the main uses of vector databases?"

# Filter to specific source
convaix ask "How do I use Claude?" --source claude

# Control context window
convaix ask "Explain embeddings" --num-chunks 10
```

#### Validate conversations
```bash
convaix validate /path/to/conversation.json
```

#### Run web UI
```bash
convaix serve

# Custom port and host
convaix serve --port 8765 --host 0.0.0.0

# Custom database
convaix serve --db postgresql://localhost/convaix
```

### Web UI

Access the web interface at `http://localhost:8000` (or configured port).

**Features:**
- **Dashboard** — browse all imported conversations, filter by source
- **Search** — hybrid search with relevance scores and snippet preview
- **Conversation view** — read full transcripts with turns and roles
- **Ask** — generate answers using Ollama with retrieved context
- **Source badges** — color-coded provider identification (Claude, ChatGPT, Gemini)

## Architecture

### Data Flow

```
Export JSON (Claude/ChatGPT/Gemini)
    ↓
Provider Parser (auto-detect + parse)
    ↓
Unified Schema (convaix v1.0)
    ↓
Chunking + Embedding (768-dim vectors)
    ↓
Database (SQLite or PostgreSQL)
    ↓
Web UI / CLI Search / RAG Retrieval
```

### Schema (convaix v1.0)

```json
{
  "schema_version": "1.0",
  "conversation": {
    "id": "unique-id",
    "source": "claude|chatgpt|gemini",
    "title": "Conversation title",
    "model": "model-name"
  },
  "turns": [
    {
      "role": "user|assistant",
      "content": "Turn content"
    }
  ],
  "statistics": {
    "turn_count": 4,
    "total_chars": 1234
  },
  "x-convaix": {
    "convaix_id": "cx_...",
    "author": {"handle": "user"},
    "created_at": "2026-04-29T..."
  }
}
```

### Database Schema

#### SQLite
- `snapshots` — conversation metadata
- `chunks` — chunked text with turn/chunk numbers
- `chunks_vec` (virtual table) — 768-dim vector storage (sqlite-vec)
- `discussions` — persistent chat sessions
- `messages` — RAG conversation history

#### PostgreSQL
- Same tables as SQLite
- `embedding vector(768)` — inline vector column on `chunks`
- HNSW indexes for O(log n) vector search
- psycopg3 connection pooling

### Providers

Each provider implements the `Provider` protocol:

```python
class Provider:
    name: str
    
    def detect(self, path: Path) -> bool:
        """Detect if file is from this provider."""
    
    def parse(self, path: Path) -> Generator[dict, None, None]:
        """Parse file and yield convaix v1.0 dicts."""
```

**Existing providers:**
- `claude.py` — handles both `text` and `content[]` fields
- `chatgpt.py` — linearizes tree-shaped `mapping` via parent pointers
- `gemini.py` — groups Takeout entries by 30-min SESSION_GAP

### Embeddings

Supports cross-platform embeddings with graceful fallback:

1. **MLX (Apple Silicon)** — `mlx-embedding-models` (fast on M-series)
2. **sentence-transformers** (default) — works on CPU/GPU, any platform

Both use **nomic-embed-text-v1.5** (768-dim, optimized for search).

```python
from convaix.embeddings import get_embedder

embedder = get_embedder()  # Auto-selects best available
embeddings = embedder.encode(texts)  # List[List[float]]
query_embedding = embedder.encode_query("search term")  # List[float]
```

### Search

**Hybrid search** combines both approaches:

1. **Keyword** — SQL `LIKE` + trigram similarity (`pg_trgm`)
2. **Semantic** — cosine similarity on embeddings (L2 distance)
3. **Ranking** — automatic relevance score (higher = more relevant)

```python
# All modes return similarity scores (0-1 scale)
results = store.search_chunks(query, mode="hybrid")
# mode: "hybrid" | "keyword" | "semantic"
```

### RAG Engine

Retrieves relevant context and generates responses:

```python
from convaix.rag.engine import RagEngine

engine = RagEngine(store)
result = engine.ask(
    "What are vector databases?",
    num_chunks=5,          # Top-k to retrieve
    source="claude"        # Filter by source
)
# result = {
#   "answer": "...",
#   "sources": [...],
#   "total_ms": 1234
# }
```

**Requirements:**
- Ollama running locally (`ollama serve`)
- Model installed (e.g., `ollama pull mistral`)

## Configuration

### Environment Variables

```bash
# Database location (default: ~/.convaix/convaix.db)
export CONVAIX_DB="sqlite:///path/to/db.sqlite"
export CONVAIX_DB="postgresql://user:pass@localhost/convaix"

# Embedder selection (default: auto)
export CONVAIX_EMBEDDER="sentence_tf"  # or "mlx"

# Ollama endpoint for RAG (default: http://localhost:11434)
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="mistral"  # or any installed model
```

### Database Connection Strings

```python
# SQLite (local file)
sqlite:///home/user/.convaix/convaix.db
sqlite:////tmp/test.db                    # Absolute path (3 slashes)

# PostgreSQL
postgresql://user:password@localhost:5432/convaix
postgresql://user@localhost/convaix       # Uses default password
```

## Development

### Setup

```bash
# Clone repo
git clone <repo> && cd convaix-app

# Install with dev extras
uv sync --extra web --extra pg --extra rag --extra embeddings --extra dev

# Activate
source .venv/bin/activate
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Exclude slow tests (embedding downloads)
pytest tests/ -v -m "not slow"

# Exclude PostgreSQL tests
pytest tests/ -v -m "not pg"

# Skip both
pytest tests/ -v -m "not slow and not pg"
```

### Code Quality

```bash
# Type checking and linting
ruff check src/ tests/

# Fix issues automatically
ruff check src/ tests/ --fix
```

### Adding a New Provider

1. Create `src/convaix/providers/myprovider.py`:
```python
from pathlib import Path
from ..schema import convert_to_schema

class MyProvider:
    name = "myprovider"
    
    def detect(self, path: Path) -> bool:
        # Check file signature/format
        return path.suffix == ".json" and "my_provider_field" in path.read_text()
    
    def parse(self, path: Path):
        # Yield convaix v1.0 dicts
        data = json.loads(path.read_text())
        for conv in data:
            yield convert_to_schema(
                source="myprovider",
                id=conv["id"],
                title=conv["title"],
                turns=conv["messages"]
            )
```

2. Register in `src/convaix/providers/__init__.py`:
```python
from .myprovider import MyProvider
PARSERS = {..., MyProvider()}
```

3. Add tests in `tests/test_providers.py`

### File Structure

```
convaix-app/
├── src/convaix/
│   ├── __init__.py
│   ├── cli.py              # Click CLI commands
│   ├── schema.py           # Conversation schema + conversion
│   ├── validate.py         # Schema validation
│   ├── chunking.py         # Text chunking strategies
│   ├── embeddings/         # Embedding models
│   │   ├── __init__.py
│   │   ├── sentence_tf.py  # sentence-transformers (default)
│   │   └── mlx_nomic.py    # MLX (Apple Silicon)
│   ├── providers/          # Provider parsers
│   │   ├── __init__.py
│   │   ├── claude.py
│   │   ├── chatgpt.py
│   │   └── gemini.py
│   ├── db/                 # Database layer
│   │   ├── __init__.py
│   │   ├── base.py         # Store protocol
│   │   ├── sqlite_store.py # SQLite implementation
│   │   └── pg_store.py     # PostgreSQL implementation
│   ├── rag/                # RAG engine
│   │   ├── __init__.py
│   │   ├── engine.py       # Retrieval + generation
│   │   └── ollama.py       # Ollama client
│   └── web/                # Web interface
│       ├── __init__.py     # FastAPI factory
│       ├── api.py          # JSON endpoints
│       └── htmx.py         # HTML templates (HTMX)
├── tests/
│   ├── conftest.py         # Fixtures
│   ├── fixtures/           # Sample data
│   ├── test_schema.py
│   ├── test_validate.py
│   ├── test_providers.py
│   └── test_db.py
├── pyproject.toml
└── README.md
```

## Examples

### Import all conversations and search

```bash
# Import from multiple sources
convaix import claude claude-export.json
convaix import chatgpt chatgpt-export.json
convaix import gemini gemini-export.json

# List what we have
convaix list
# Output:
# ┏━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┓
# ┃ #   ┃ Source ┃ Title          ┃ Turns┃ Date     ┃
# ┣━━━━━╋━━━━━━━━╋━━━━━━━━━━━━━━━━╋━━━━━╋━━━━━━━━━━┫
# ┃ 1   ┃ claude │ Vector DBs     ┃ 4   ┃ 2026-04-29┃
# ┃ 2   ┃ chatgpt│ Python async   ┃ 6   ┃ 2026-04-28┃
# ┣━━━━━╋━━━━━━━━╋━━━━━━━━━━━━━━━━╋━━━━━╋━━━━━━━━━━┫

# Search across all
convaix search "how to use embeddings"
# Returns: 8 chunks from 3 conversations with similarity scores

# Ask a question
convaix ask "Compare embeddings across my conversations"
# Uses RAG to synthesize answer from corpus
```

### Run with PostgreSQL for production

```bash
# Create database and install pgvector
createdb convaix
psql convaix -c "CREATE EXTENSION IF NOT EXISTS vector"

# Import with pgvector
convaix import claude export.json \
  --db postgresql://user@localhost/convaix

# Serve with connection pooling
convaix serve --db postgresql://user@localhost/convaix
```

### Programmatic usage

```python
from pathlib import Path
from convaix.db import get_store
from convaix.providers import detect_parser
from convaix.schema import add_convaix_extension
from convaix.validate import validate_conversation

# Load and validate
parser = detect_parser(Path("export.json"))
conv_data = next(parser.parse(Path("export.json")))
validate_conversation(conv_data)

# Store
store = get_store("sqlite:///my.db")
add_convaix_extension(conv_data, author_handle="me")
if store.load_snapshot(conv_data):
    store.chunk_snapshot(conv_data)

# Search
results = store.search_chunks("embeddings", mode="semantic", limit=5)
for r in results:
    print(f"{r['similarity']:.3f} — {r['chunk_text']}")

store.close()
```

## Performance

### Benchmarks (on 4-core CPU, SQLite)

- **Import** — ~2 seconds per conversation (with embeddings)
- **Chunk** — ~10 paragraphs/second
- **Embed** — ~50 chunks/second (sentence-transformers on CPU)
- **Search** — <100ms (hybrid)
  - Keyword-only: <10ms
  - Semantic: <100ms (L2 distance on 768-dim)

### Optimization Tips

1. **Use `--skip-embeddings`** for keyword-only search (10x faster import)
2. **Use PostgreSQL + HNSW** for large corpora (>100k chunks)
3. **Use MLX on Apple Silicon** (4-6x faster embeddings on M-series)
4. **Batch imports** — import multiple files before searching

## Troubleshooting

### "ModuleNotFoundError: No module named 'sentence_transformers'"
```bash
uv pip install sentence-transformers torch
```

### "No module named 'einops'"
```bash
uv pip install einops
```

### "Ollama connection refused"
```bash
# Make sure Ollama is running
ollama serve

# Check endpoint
curl http://localhost:11434/api/tags
```

### SQLite "database is locked"
- Close other connections to the database
- Or use PostgreSQL for concurrent access

### Slow searches
- Add `--skip-embeddings` to imports if semantic search isn't needed
- Use PostgreSQL with HNSW indexes
- Reduce `--limit` if retrieving too many results

## Roadmap

- [ ] **v0.3** — Desktop app (Tauri) with local Ollama
- [ ] **v0.4** — Multi-user support + API auth
- [ ] **v0.5** — Notion, Slack, Discord imports
- [ ] **v1.0** — Production release

## License

MIT — See LICENSE file

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Ensure `ruff check` and `pytest` pass
5. Open a pull request

## Credits

- **convaix schema** — open format for AI conversations
- **sentence-transformers** — nomic embeddings
- **sqlite-vec** — vector search for SQLite
- **pgvector** — vector search for PostgreSQL
- **FastAPI** — modern Python web framework
- **HTMX** — interactive HTML without JS frameworks

## Support

- **Issues** — GitHub Issues for bugs and features
- **Discussions** — GitHub Discussions for questions
- **Documentation** — See README and source code comments

---

**Happy searching! 🔍**
