# M0 — Setup & Spike

Goal: green local dev loop on both backends before writing a single line of
provider code.

## Tasks

### 0.1 — Fork / clone, install convaix in editable mode
- `cd convaix && python -m venv .venv && source .venv/bin/activate`
- `pip install -e .[providers,embeddings]` (note: `embeddings` extra is
  Apple-only today — see 0.4 below)
- Verify CLI registered: `convaix --help`

### 0.2 — Run existing test suite
- `pip install pytest`
- `pytest -m "not slow"` from `convaix/`
- Capture which tests assume Apple / MLX and tag accordingly. We will
  un-tag them in M1 once the embedder is portable.

### 0.3 — docker-compose for Postgres + pgvector
- Add `docker-compose.yml` at convaix root:
  ```yaml
  services:
    db:
      image: pgvector/pgvector:pg16
      environment:
        POSTGRES_PASSWORD: convaix
        POSTGRES_DB: convaix
      ports: ["5432:5432"]
      volumes: ["pgdata:/var/lib/postgresql/data"]
  volumes: { pgdata: {} }
  ```
- `docker compose up -d`, confirm `psql` and `CREATE EXTENSION vector;` work.

### 0.4 — Cross-platform embedder spike
- Try `sentence-transformers` with `nomic-ai/nomic-embed-text-v1.5` on Linux.
  Confirm 768-dim output, both `search_document:` and `search_query:`
  prefixes behave the same as the MLX version.
- If sentence-transformers is too heavy at install time (~2 GB torch), spike
  `nomic-embed-text-v1.5` via `gguf` + `llama-cpp-python` as a smaller
  alternative.
- Record the decision in `architecture.md` if anything changes.

### 0.5 — Sample data corpus
- Get one real export file per provider into `convaix/tests/fixtures/`:
  - `tests/fixtures/claude_sample.json` — full Anthropic export
  - `tests/fixtures/chatgpt_sample.json` — OpenAI conversations.json
  - `tests/fixtures/gemini_sample.html` — Google Takeout MyActivity export
- These can be Nitin's own exports, redacted if needed. M1 parsers test
  against these fixtures.

### 0.6 — Smoke-test the full path with synthetic data
- Generate a v1.0-shaped JSON via `schema.convert_to_schema(...)`.
- `convaix load <synthetic.json>` → verify SQLite snapshot + chunks land.
- `convaix search "<some keyword>"` → verify hit comes back.
- This is our regression baseline before refactoring.

## Definition of done

- `pytest -m "not slow"` passes.
- `docker compose up -d` brings Postgres up; `psql -c "SELECT extname FROM pg_extension;"` shows `vector`.
- One synthetic v1.0 conversation makes it through `load → list → search`.
- One sample fixture per provider lives under `tests/fixtures/`.
- Embedding decision (768-dim nomic, MLX or sentence-transformers) is
  documented and reproducible on the dev machine.

## Out of scope for M0

- Anything provider-specific (parsing real exports). That's M1.
- Postgres adapter code. That's M2.
- Web UI. That's M3.
