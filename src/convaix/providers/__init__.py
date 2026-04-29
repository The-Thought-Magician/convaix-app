"""Provider registry — maps provider names to parser instances."""

from pathlib import Path

from .claude import ClaudeParser
from .chatgpt import ChatGPTParser
from .gemini import GeminiParser

PARSERS: dict = {
    "claude": ClaudeParser(),
    "chatgpt": ChatGPTParser(),
    "gemini": GeminiParser(),
}


def get_parser(name: str):
    if name not in PARSERS:
        raise ValueError(f"Unknown provider: {name!r}. Known: {list(PARSERS)}")
    return PARSERS[name]


def detect_parser(path: Path):
    """Return the first parser whose detect() accepts path, or None."""
    for p in PARSERS.values():
        if p.detect(path):
            return p
    return None
