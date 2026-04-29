"""Parser for OpenAI (ChatGPT) conversations.json export.

The export is an array of conversations where each conversation has a
tree-shaped 'mapping' dict rather than a flat list. We linearize by
following the current_node leaf up to the root, then reversing.

Shape:
{
  "title": "...",
  "create_time": 1700000000.0,
  "update_time": ...,
  "id": "conv-uuid",
  "current_node": "node-uuid",
  "mapping": {
    "node-uuid": {
      "id": "...",
      "parent": "parent-uuid" | null,
      "children": [...],
      "message": {
        "id": "...",
        "author": {"role": "user" | "assistant" | "system" | "tool"},
        "content": {"content_type": "text", "parts": ["..."]},
        "create_time": ...,
      } | null
    }
  }
}
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..schema import convert_to_schema

logger = logging.getLogger(__name__)

KEEP_ROLES = {"user", "assistant", "system"}


def _ts_to_iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def _extract_text(message: dict) -> str:
    content = message.get("content", {})
    if isinstance(content, str):
        return content
    parts = content.get("parts", [])
    return "\n\n".join(str(p) for p in parts if isinstance(p, str) and p.strip())


def _linearize(mapping: dict, current_node: str | None) -> list[dict]:
    """Walk from current_node to root, collecting messages; return root-first order."""
    if not current_node or current_node not in mapping:
        all_nodes = list(mapping.values())
        roots = [n for n in all_nodes if not n.get("parent")]
        if not roots:
            return []
        current_node = roots[0]["id"]
        while True:
            children = mapping[current_node].get("children", [])
            if not children:
                break
            current_node = children[-1]

    path = []
    node_id = current_node
    visited = set()
    while node_id and node_id in mapping and node_id not in visited:
        visited.add(node_id)
        node = mapping[node_id]
        msg = node.get("message")
        if msg:
            path.append(msg)
        node_id = node.get("parent")

    path.reverse()
    return path


class ChatGPTParser:
    name = "chatgpt"

    def detect(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, list) or not data:
                return False
            first = data[0]
            return "mapping" in first and "title" in first
        except Exception:
            return False

    def parse(self, path: Path) -> Iterator[dict]:
        with open(path) as f:
            conversations = json.load(f)

        if not isinstance(conversations, list):
            conversations = [conversations]

        for conv in conversations:
            conv_id = conv.get("id", "")
            title = conv.get("title") or "Untitled"
            created_at = _ts_to_iso(conv.get("create_time"))
            mapping = conv.get("mapping", {})
            current_node = conv.get("current_node")

            messages = _linearize(mapping, current_node)

            turns = []
            branch_count = 0
            for msg in messages:
                role = msg.get("author", {}).get("role", "")
                if role not in KEEP_ROLES:
                    continue
                text = _extract_text(msg)
                if not text.strip():
                    continue
                turns.append({
                    "role": role,
                    "content": text,
                    "timestamp": _ts_to_iso(msg.get("create_time")),
                    "metadata": {"id": msg.get("id", "")},
                })

            # count branch nodes (children > 1) for metadata
            for node in mapping.values():
                if len(node.get("children", [])) > 1:
                    branch_count += 1

            if not turns:
                logger.debug("Skipping empty conversation: %s", conv_id)
                continue

            yield convert_to_schema(
                source="chatgpt",
                source_id=conv_id,
                title=title,
                turns=turns,
                created_at=created_at,
                extra_metadata={
                    "branch_count": branch_count,
                    "linearization": "current_leaf_path",
                },
            )
