"""ProviderParser ABC."""

from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class ProviderParser(Protocol):
    name: str

    def detect(self, path: Path) -> bool:
        """Return True if path looks like an export from this provider."""
        ...

    def parse(self, path: Path) -> Iterator[dict]:
        """Yield convaix schema v1.0 dicts."""
        ...
