"""Conversation schema v1.0 — shared contract for all provider outputs."""

import hashlib
import re
import uuid
from datetime import datetime, timezone

ROLE_MAP = {
    "model": "assistant",
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "human": "user",
}


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len]


def generate_conv_id(source: str, source_id: str) -> str:
    """Stable, platform-agnostic conversation ID — same source+source_id always produces same ID."""
    digest = hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()[:12]
    return f"conv_{digest}"


def generate_convaix_id() -> str:
    return f"cx_{uuid.uuid4()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def convert_to_schema(
    source: str,
    source_id: str | None,
    title: str,
    turns: list[dict],
    *,
    source_url: str | None = None,
    model: str | None = None,
    created_at: str | None = None,
    extra_metadata: dict | None = None,
) -> dict:
    schema_turns = []
    for i, turn in enumerate(turns):
        role = ROLE_MAP.get(turn.get("role", "unknown"), turn.get("role", "unknown"))
        schema_turns.append(
            {
                "turn_number": i + 1,
                "role": role,
                "content": turn.get("content", ""),
                "timestamp": turn.get("timestamp"),
                "attachments": turn.get("attachments", []),
                "metadata": turn.get("metadata", {}),
            }
        )

    user_turns = sum(1 for t in schema_turns if t["role"] == "user")
    assistant_turns = sum(1 for t in schema_turns if t["role"] == "assistant")
    total_chars = sum(len(t["content"]) for t in schema_turns)

    effective_source_id = source_id or hashlib.sha256(title.encode()).hexdigest()[:16]
    conv_id = generate_conv_id(source, effective_source_id)

    return {
        "schema_version": "1.0",
        "conversation": {
            "id": conv_id,
            "title": title,
            "source": source,
            "source_id": source_id,
            "source_url": source_url,
            "model": model,
            "created_at": created_at,
            "exported_at": _now_iso(),
            "tags": [],
            "metadata": extra_metadata or {},
        },
        "turns": schema_turns,
        "statistics": {
            "turn_count": len(schema_turns),
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "total_chars": total_chars,
        },
    }


def add_convaix_extension(conv_data: dict, author_handle: str, parent_refs: list | None = None) -> dict:
    conv_data["x-convaix"] = {
        "convaix_id": generate_convaix_id(),
        "version": "0.2",
        "conv_id": conv_data["conversation"]["id"],
        "author": {"handle": author_handle, "key_id": None},
        "published_at": _now_iso(),
        "parent_refs": parent_refs or [],
        "annotations": [],
        "signature": None,
    }
    return conv_data
