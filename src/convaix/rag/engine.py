"""RAG engine — retrieve from Store, generate with Ollama."""

import logging
import time

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a helpful assistant. Answer the user's question using the provided "
    "conversation excerpts as your sources. Cite sources as [Source N]. "
    "If the excerpts do not contain the answer, say so clearly."
)

MAX_CHUNK_CHARS = 600


class RagEngine:
    def __init__(self, store, ollama=None):
        self.store = store
        if ollama is None:
            from .ollama import OllamaClient
            ollama = OllamaClient()
        self.ollama = ollama

    def ask(
        self,
        query: str,
        *,
        discussion_id: str | None = None,
        source: str | None = None,
        num_chunks: int = 5,
        author: str = "user",
    ) -> dict:
        t0 = time.time()

        chunks = self.store.search_chunks(query, source=source, limit=num_chunks, mode="hybrid")
        retrieval_ms = int((time.time() - t0) * 1000)

        context = self._format_context(chunks)
        prompt = self._build_prompt(query, context)

        t1 = time.time()
        answer = self.ollama.generate(prompt)
        generation_ms = int((time.time() - t1) * 1000)

        if discussion_id:
            self.store.add_discussion_message(discussion_id, author, query)
            self.store.add_discussion_message(discussion_id, "assistant", answer)

        sources = [
            {
                "convaix_id": c.get("convaix_id", ""),
                "title": c.get("title", ""),
                "source": c.get("source", ""),
                "role": c.get("role", ""),
                "snippet": c.get("chunk_text", "")[:300],
                "similarity": round(c.get("similarity", 0.0), 4),
                "match_type": c.get("match_type", "kw"),
            }
            for c in chunks
        ]

        return {
            "answer": answer,
            "sources": sources,
            "discussion_id": discussion_id,
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
            "total_ms": retrieval_ms + generation_ms,
        }

    def _format_context(self, chunks: list[dict]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            snippet = c.get("chunk_text", "")[:MAX_CHUNK_CHARS]
            parts.append(
                f"[Source {i}] From: {c.get('title', '?')} ({c.get('source', '?')})\n"
                f"Role: {c.get('role', '?')} | Similarity: {c.get('similarity', 0):.3f}\n\n"
                f"{snippet}"
            )
        return "\n\n---\n\n".join(parts)

    def _build_prompt(self, query: str, context: str) -> str:
        return (
            f"{_SYSTEM}\n\n"
            f"RETRIEVED CONVERSATION EXCERPTS:\n{context}\n\n"
            f"QUESTION: {query}\n\nANSWER:"
        )
