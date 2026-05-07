"""Paragraph-level chunking for conversation turns."""


def _split_at_sentences(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries to stay under max_chars."""
    sentences = text.split(". ")
    chunks = []
    current = ""
    for i, sent in enumerate(sentences):
        piece = sent if i == len(sentences) - 1 else sent + ". "
        if current and len(current) + len(piece) > max_chars:
            chunks.append(current.rstrip())
            current = piece
        else:
            current += piece
    if current:
        chunks.append(current.rstrip())
    return [c for c in chunks if c]


def split_into_chunks(content: str, min_chars: int = 50, max_chars: int = 2000) -> list[str]:
    if not content or not content.strip():
        return []

    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    merged = [paragraphs[0]]
    for p in paragraphs[1:]:
        if len(p) < min_chars:
            merged[-1] = merged[-1] + "\n\n" + p
        else:
            merged.append(p)

    result = []
    for chunk in merged:
        if len(chunk) > max_chars:
            result.extend(_split_at_sentences(chunk, max_chars))
        else:
            result.append(chunk)

    return result
