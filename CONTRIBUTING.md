# Contributing to convaix

Thanks for your interest in contributing. convaix is open-source (MIT) and welcomes PRs, bug reports, and provider parsers.

## Development setup

```bash
git clone https://github.com/chiranjeetmishra/convaix.git
cd convaix
uv sync --extra web --extra rag --extra embeddings
uv run convaix --help
```

Run tests:

```bash
uv run pytest tests/ -v
```

Run the linter:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Project structure

```
src/convaix/
  cli.py           # click CLI entry point
  schema.py        # convaix v1.0 schema helpers
  validate.py      # schema validator
  chunking.py      # text splitting
  providers/       # import parsers (claude, chatgpt, gemini)
  db/              # SQLite and Postgres store implementations
  embeddings/      # nomic-embed-text-v1.5 (sentence-tf or MLX)
  rag/             # Ollama RAG engine
  web/             # FastAPI + HTMX web UI
tests/
  conftest.py      # fixtures and sample data
  fixtures/        # sample export files per provider
```

## Adding a new provider parser

1. Create `src/convaix/providers/<name>.py` with a class that extends `BaseParser`
2. Implement `detect(path: Path) -> bool` and `parse(path: Path) -> Iterator[dict]`
3. Each yielded dict must be a valid convaix v1.0 document (see `schema.py`)
4. Register the parser in `src/convaix/providers/__init__.py`
5. Add a fixture export file under `tests/fixtures/<name>/`
6. Add tests in `tests/test_providers.py`

## Commit style

```
type: short description

Types: feat, fix, docs, chore, test, refactor
```

One commit per logical change. Keep commits small and reviewable.

## Pull request checklist

- [ ] `uv run ruff check src/ tests/` passes with no errors
- [ ] `uv run pytest tests/` passes
- [ ] New provider parsers include at least one fixture + test
- [ ] No secrets or personal data in fixtures

## Reporting bugs

Open a GitHub issue with:
- convaix version (`convaix --version`)
- OS and Python version
- Minimal reproduction steps
- Expected vs actual behaviour

## Questions

Open a GitHub Discussion — issues are for bugs and feature requests only.
