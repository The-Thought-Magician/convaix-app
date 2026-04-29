"""Embedder factory. Always 768-dim nomic-embed-text-v1.5."""

import os

EMBEDDING_DIM = 768


def get_embedder(prefer: str | None = None):
    """Return an Embedder. prefer: 'mlx' | 'sentence_tf' | 'auto' (default)."""
    pref = prefer or os.getenv("CONVAIX_EMBEDDER", "auto")
    if pref in ("mlx", "auto"):
        try:
            from .mlx_nomic import MlxNomic
            embedder = MlxNomic()
            embedder.encode_query("test")  # Verify mlx_embedding_models is available
            return embedder
        except (ImportError, ModuleNotFoundError):
            if pref == "mlx":
                raise
    from .sentence_tf import SentenceTfNomic
    return SentenceTfNomic()
