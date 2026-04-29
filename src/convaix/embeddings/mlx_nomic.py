"""Apple Silicon embedder via mlx-embedding-models (768-dim). Faster on M-series Macs."""

import logging
import os

os.environ.setdefault("USE_TF", "0")

logger = logging.getLogger(__name__)

MODEL_NAME = "nomic-text-v1.5"
EMBEDDING_DIM = 768

_model = None


def _patch_seq_lens():
    import mlx_embedding_models.embedding as _m
    _m.SEQ_LENS = sorted(set(_m.SEQ_LENS + [640, 768, 896, 1024, 1280, 1536, 1792, 2048]))


def _get_model():
    global _model
    if _model is None:
        _patch_seq_lens()
        from mlx_embedding_models.embedding import EmbeddingModel
        logger.info(f"Loading {MODEL_NAME} (MLX)...")
        _model = EmbeddingModel.from_registry(MODEL_NAME)
        logger.info(f"Model loaded (dim={EMBEDDING_DIM})")
    return _model


class MlxNomic:
    dim = EMBEDDING_DIM

    def encode(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        model = _get_model()
        prefixed = [f"search_document: {t}" for t in texts]
        return model.encode(prefixed, batch_size=batch_size, show_progress=False).tolist()

    def encode_query(self, text: str) -> list[float]:
        model = _get_model()
        return model.encode([f"search_query: {text}"], show_progress=False).tolist()[0]
