"""Paragraph-level chunking for conversation turns."""


def split_into_chunks(content: str, min_chars: int = 50) -> list[str]:
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

    return merged
