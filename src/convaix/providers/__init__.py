"""Provider registry — maps provider names to parser instances.

The order parsers are tried in detect_parser() matters: more specific parsers
must come first. For example, Claude's export format is distinct enough to
identify before falling through to the more generic Gemini heuristic. Always
register the most specific (least ambiguous) parsers at the top of PARSERS.
"""

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
