"""convaix CLI."""

import json
import logging
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)

DEFAULT_DB = os.getenv("CONVAIX_DB", f"sqlite://{Path.home()}/.convaix/convaix.db")


_STAR_SENTINEL = Path.home() / ".convaix" / ".starred_nudge"


def _maybe_nudge_star():
    if not _STAR_SENTINEL.exists():
        console.print(
            "\n[dim]⭐  If convaix is useful, a GitHub star helps others find it → "
            "https://github.com/chiranjeetmishra/convaix[/dim]\n"
        )
        _STAR_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        _STAR_SENTINEL.touch()


@click.group()
@click.version_option(package_name="convaix")
@click.pass_context
def main(ctx):
    """convaix — import, search, and chat over AI conversations."""
    if ctx.invoked_subcommand == "import":
        _maybe_nudge_star()


# ── import ──────────────────────────────────────────────────────────────────

@main.command("import")
@click.argument("provider")
@click.argument("path", type=click.Path(exists=True))
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--author", default=os.getenv("USER", "local"))
@click.option("--skip-embeddings", is_flag=True)
def import_cmd(provider, path, db, author, skip_embeddings):
    """Import conversations from a provider export (claude/chatgpt/gemini/auto)."""
    from .db import get_store
    from .providers import detect_parser, get_parser
    from .schema import add_convaix_extension
    from .validate import ValidationError, validate_conversation

    p = Path(path)
    parser = detect_parser(p) if provider == "auto" else get_parser(provider)
    store = get_store(db)

    loaded = skipped = errors = 0
    for conv_data in parser.parse(p):
        try:
            validate_conversation(conv_data)
            if "x-convaix" not in conv_data:
                add_convaix_extension(conv_data, author_handle=author)
            if store.load_snapshot(conv_data):
                store.chunk_snapshot(conv_data, skip_embeddings=skip_embeddings)
                console.print(f"  [green]✓[/green] {conv_data['conversation']['title'][:60]}")
                loaded += 1
            else:
                skipped += 1
        except (ValidationError, Exception) as e:
            console.print(f"  [red]✗[/red] {e}")
            errors += 1

    store.close()
    t = Table(title="Import Summary")
    t.add_column("Metric", style="cyan")
    t.add_column("Count", style="green")
    t.add_row("Loaded", str(loaded))
    t.add_row("Skipped (duplicate)", str(skipped))
    t.add_row("Errors", str(errors))
    console.print(t)


# ── load (raw v1.0 JSON) ─────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--skip-embeddings", is_flag=True)
def load(path, db, skip_embeddings):
    """Load already-converted convaix v1.0 JSON files."""
    from .db import get_store
    from .schema import add_convaix_extension
    from .validate import ValidationError, validate_conversation

    store = get_store(db)
    files = sorted(Path(path).glob("*.json")) if Path(path).is_dir() else [Path(path)]
    loaded = skipped = errors = 0
    for fp in files:
        try:
            data = json.loads(fp.read_text())
            validate_conversation(data)
            if "x-convaix" not in data:
                add_convaix_extension(data, author_handle="local")
            if store.load_snapshot(data):
                store.chunk_snapshot(data, skip_embeddings=skip_embeddings)
                console.print(f"  [green]Loaded[/green]: {fp.name}")
                loaded += 1
            else:
                skipped += 1
        except (ValidationError, json.JSONDecodeError) as e:
            console.print(f"  [red]Error[/red]: {fp.name}: {e}")
            errors += 1
    store.close()
    console.print(f"[bold]Done[/bold]: {loaded} loaded, {skipped} skipped, {errors} errors")


# ── list ─────────────────────────────────────────────────────────────────────

@main.command("list")
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--source", "-s")
def list_cmd(db, source):
    """List imported conversations."""
    from .db import get_store
    store = get_store(db)
    rows = store.list_snapshots(source=source)
    store.close()
    if not rows:
        console.print("[yellow]No conversations found.[/yellow]")
        return
    t = Table(title="Conversations")
    t.add_column("#", style="dim")
    t.add_column("Source", style="magenta")
    t.add_column("Title", style="blue", ratio=2)
    t.add_column("Turns", style="green")
    t.add_column("Date", style="dim")
    t.add_column("ID", style="dim")
    for i, r in enumerate(rows, 1):
        t.add_row(str(i), r["source"], r["title"][:50], str(r["turn_count"]),
                  (r.get("published_at") or "")[:10], r["convaix_id"][:16] + "…")
    console.print(t)


# ── search ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--source", "-s")
@click.option("--limit", "-l", default=10, type=int)
@click.option("--mode", default="hybrid", type=click.Choice(["hybrid", "keyword", "semantic"]))
def search(query, db, source, limit, mode):
    """Search across imported conversations."""
    from .db import get_store
    q = " ".join(query)
    store = get_store(db)
    results = store.search_chunks(q, source=source, limit=limit, mode=mode)
    store.close()
    if not results:
        console.print("[yellow]No results.[/yellow]")
        return
    t = Table(title=f'Search: "{q}"', show_lines=True)
    t.add_column("Sim", style="green", no_wrap=True)
    t.add_column("Src", style="magenta")
    t.add_column("Title", style="blue", max_width=30)
    t.add_column("Content", ratio=2)
    for r in results:
        t.add_row(f"{r.get('similarity', 0):.3f}", r["source"],
                  r["title"][:30], r["chunk_text"][:200])
    console.print(t)


# ── validate ──────────────────────────────────────────────────────────────────

@main.command()
@click.argument("file_path", type=click.Path(exists=True))
def validate(file_path):
    """Validate a convaix v1.0 JSON file."""
    from .validate import validate_conversation
    try:
        data = json.loads(Path(file_path).read_text())
        validate_conversation(data)
        console.print(f"[green]Valid[/green]: {file_path}")
    except Exception as e:
        console.print(f"[red]Invalid[/red]: {e}")
        raise SystemExit(1)


# ── ask ───────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("question")
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--source", "-s")
@click.option("--num-chunks", default=5, type=int)
def ask(question, db, source, num_chunks):
    """Ask a question against your imported corpus (requires Ollama)."""
    from .db import get_store
    from .rag.engine import RagEngine
    store = get_store(db)
    engine = RagEngine(store)
    result = engine.ask(question, source=source, num_chunks=num_chunks)
    console.print(f"\n[bold]Answer[/bold]:\n{result['answer']}\n")
    if result["sources"]:
        t = Table(title="Sources")
        t.add_column("Src", style="magenta")
        t.add_column("Title", style="blue")
        t.add_column("Sim", style="green")
        t.add_column("Type", style="dim")
        for s in result["sources"]:
            t.add_row(s["source"], s["title"][:40], str(s["similarity"]), s["match_type"])
        console.print(t)
    console.print(f"[dim]{result['total_ms']}ms total[/dim]")
    store.close()


# ── serve ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--db", default=DEFAULT_DB, envvar="CONVAIX_DB")
@click.option("--port", default=8000, type=int)
@click.option("--host", default="127.0.0.1")
def serve(db, port, host):
    """Run the convaix web app."""
    import uvicorn
    from .web import create_app
    console.print(f"[bold green]Starting convaix web app[/bold green] → http://{host}:{port}")
    uvicorn.run(create_app(db), host=host, port=port)
