"""RAG engine tests."""
from unittest.mock import MagicMock, patch


def _make_store(chunks=None):
    store = MagicMock()
    store.search_chunks.return_value = chunks or [
        {
            "convaix_id": "abc123",
            "title": "Test Conv",
            "source": "claude",
            "role": "user",
            "chunk_text": "Hello world",
            "similarity": 0.9,
            "match_type": "kw",
        }
    ]
    return store


def test_ask_returns_expected_keys():
    from convaix.rag.engine import RagEngine
    from convaix.rag.ollama import OllamaClient

    ollama = MagicMock(spec=OllamaClient)
    ollama.is_available.return_value = True
    ollama.generate.return_value = "This is the answer."

    store = _make_store()
    engine = RagEngine(store, ollama=ollama)
    result = engine.ask("What is this?")

    assert "answer" in result
    assert "sources" in result
    assert "total_ms" in result
    assert result["answer"] == "This is the answer."
    assert isinstance(result["sources"], list)


def test_ask_no_llm_fallback():
    from convaix.rag.engine import RagEngine
    from convaix.rag.ollama import OllamaClient
    import os

    ollama = MagicMock(spec=OllamaClient)
    ollama.is_available.return_value = False

    store = _make_store()
    engine = RagEngine(store, ollama=ollama)

    # No CONVAIX_LLM set => no LLM available message
    env = {k: v for k, v in os.environ.items() if k != "CONVAIX_LLM"}
    with patch.dict(os.environ, env, clear=True):
        result = engine.ask("What is this?")

    assert "No LLM available" in result["answer"]
    assert result["sources"] == []
    assert result["total_ms"] == 0
