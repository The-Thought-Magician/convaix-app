"""Store factory. Accepts sqlite:// or postgresql:// URLs."""

import os
from pathlib import Path

DEFAULT_SQLITE_PATH = Path.home() / ".convaix" / "convaix.db"


def get_store(url: str | None = None):
    url = url or os.getenv("CONVAIX_DB", f"sqlite://{DEFAULT_SQLITE_PATH}")
    if not url.startswith(("sqlite://", "postgresql://", "postgres://")):
        url = f"sqlite://{url}"

    if url.startswith("sqlite://"):
        from .sqlite_store import SqliteStore
        path = url.removeprefix("sqlite://").replace("~", str(Path.home()))
        return SqliteStore(path)

    if url.startswith(("postgresql://", "postgres://")):
        from .pg_store import PgStore
        return PgStore(url)

    raise ValueError(f"Unsupported DB URL scheme: {url}")
