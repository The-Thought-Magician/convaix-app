"""Parser for Anthropic (Claude) conversation export JSON.

Export shape (array of conversations):
[
  {
    "uuid": "...",
    "name": "Conversation title",
    "created_at": "2024-...",
    "updated_at": "2024-...",
    "chat_messages": [
      {
        "uuid": "...",
        "sender": "human" | "assistant",
        "text": "...",              # older exports
        "content": [{"type": "text", "text": "..."}],  # newer
        "created_at": "..."
      }
    ]
  }
]
"""

import json
import logging
from pathlib import Path
from typing import Iterator

from ..schema import convert_to_schema

logger = logging.getLogger(__name__)

ROLE_MAP = {"human": "user", "assistant": "assistant"}


def _extract_text(msg: dict) -> str:
    if "text" in msg and isinstance(msg["text"], str):
        return msg["text"]
    content = msg.get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n\n".join(parts)
    return ""


class ClaudeParser:
    name = "claude"

    def detect(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, list) or not data:
                return False
            first = data[0]
            return "chat_messages" in first and "uuid" in first
        except Exception:
            return False

    def parse(self, path: Path) -> Iterator[dict]:
        with open(path) as f:
            conversations = json.load(f)

        if not isinstance(conversations, list):
            conversations = [conversations]

        for conv in conversations:
            uuid = conv.get("uuid", "")
            title = conv.get("name") or "Untitled"
            created_at = conv.get("created_at")
            chat_messages = conv.get("chat_messages", [])

            turns = []
            for msg in chat_messages:
                sender = msg.get("sender", "")
                role = ROLE_MAP.get(sender, "user")
                text = _extract_text(msg)
                if not text.strip():
                    continue
                turns.append({
                    "role": role,
                    "content": text,
                    "timestamp": msg.get("created_at"),
                    "metadata": {"uuid": msg.get("uuid", "")},
                })

            if not turns:
                logger.debug("Skipping empty conversation: %s", uuid)
                continue

            yield convert_to_schema(
                source="claude",
                source_id=uuid,
                title=title,
                turns=turns,
                created_at=created_at,
                extra_metadata={"raw_message_count": len(chat_messages)},
            )
