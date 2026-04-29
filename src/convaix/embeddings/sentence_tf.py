"""Cross-platform embedder using sentence-transformers + nomic-embed-text-v1.5 (768-dim)."""

import logging
import os

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logger = logging.getLogger(__name__)

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading {MODEL_NAME} (sentence-transformers)...")
        _model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
        logger.info(f"Model loaded (dim={EMBEDDING_DIM})")
    return _model


class SentenceTfNomic:
    dim = EMBEDDING_DIM

    def encode(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        model = _get_model()
        prefixed = [f"search_document: {t}" for t in texts]
        embs = model.encode(prefixed, batch_size=batch_size, show_progress_bar=False)
        return embs.tolist()

    def encode_query(self, text: str) -> list[float]:
        model = _get_model()
        embs = model.encode([f"search_query: {text}"], show_progress_bar=False)
        return embs.tolist()[0]
