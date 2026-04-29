"""Embedder ABC."""

from typing import Protocol, runtime_checkable

EMBEDDING_DIM = 768


@runtime_checkable
class Embedder(Protocol):
    dim: int

    def encode(self, texts: list[str], batch_size: int = 64) -> list[list[float]]: ...
    def encode_query(self, text: str) -> list[float]: ...
