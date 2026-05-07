# Self-Hosting convaix

convaix is fully self-hostable. All core features — import, search, RAG, and the web UI — run entirely on your machine with no external services required.

## Quick start (SQLite, recommended for personal use)

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
git clone https://github.com/chiranjeetmishra/convaix.git
cd convaix
uv sync
uv run convaix --help
```

Start the web UI:

```bash
uv run uvicorn convaix.web:create_app --factory --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

---

## With PostgreSQL + pgvector (recommended for teams)

Requires Docker.

```bash
# Start Postgres with pgvector
docker-compose up -d

# Set the database URL
export CONVAIX_DB_URL="postgresql://convaix:convaix@localhost:5432/convaix"

# Run the app
uv run uvicorn convaix.web:create_app --factory --host 0.0.0.0 --port 8000
```

The `docker-compose.yml` in the repo sets up Postgres 16 with pgvector pre-installed.

---

## Docker (all-in-one)

> Note: A Docker image is planned. Until then, use the steps above.

---

## Semantic search (embeddings)

By default, convaix uses keyword search only. To enable semantic search:

```bash
uv pip install sentence-transformers einops
```

On first use, the `nomic-embed-text-v1.5` model (~270 MB) is downloaded automatically from HuggingFace. It runs locally — no API key needed.

**Apple Silicon (MLX):** Install `mlx-embedding-models` for faster inference:

```bash
uv pip install mlx-embedding-models
```

convaix auto-detects and uses MLX when available.

---

## RAG / "Ask your archive"

Requires a running [Ollama](https://ollama.com) instance:

```bash
ollama pull llama3
```

Then set in your environment:

```bash
export CONVAIX_OLLAMA_URL="http://localhost:11434"
export CONVAIX_OLLAMA_MODEL="llama3"
```

Or add these to a `.env` file (see `.env.example`).

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CONVAIX_DB_URL` | SQLite at `~/.convaix/convaix.db` | Database URL |
| `CONVAIX_EMBEDDER` | `auto` | `auto`, `sentence_tf`, or `mlx` |
| `CONVAIX_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `CONVAIX_OLLAMA_MODEL` | `llama3` | Ollama model to use for RAG |

---

## Upgrading

```bash
git pull
uv sync
```

Database migrations are applied automatically on startup.

---

## Data location

By default, all data is stored at:

```
~/.convaix/
  convaix.db       # SQLite database (snapshots, chunks, embeddings)
```

Back up this file to preserve your archive.

---

## Security

- convaix binds to `0.0.0.0` when started with `--host 0.0.0.0` — put it behind a reverse proxy (nginx, Caddy) with HTTPS and auth if exposing beyond localhost.
- No data leaves your machine. All embeddings and search run locally.

---

## Community

- Issues and PRs welcome on GitHub
- For self-hosting questions, open a GitHub Discussion
