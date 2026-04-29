"""Parser for Google Gemini via Google Takeout.

Takeout gives either:
  - MyActivity.json — list of activity entries (used if available)
  - MyActivity.html — HTML with prompt/response entries (fallback)

Because Takeout doesn't natively group prompts into conversations, we
group by consecutive entries within a 30-minute window and emit one
conversation per group. Accuracy may vary.
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterator

from ..schema import convert_to_schema

logger = logging.getLogger(__name__)

# Max gap between entries to consider them part of the same conversation
SESSION_GAP = timedelta(minutes=30)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _ts_iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _group_into_sessions(entries: list[dict]) -> list[list[dict]]:
    if not entries:
        return []
    sessions, current = [], [entries[0]]
    for entry in entries[1:]:
        prev_ts = _parse_iso(current[-1].get("time"))
        this_ts = _parse_iso(entry.get("time"))
        if prev_ts and this_ts and (this_ts - prev_ts) <= SESSION_GAP:
            current.append(entry)
        else:
            sessions.append(current)
            current = [entry]
    sessions.append(current)
    return sessions


def _parse_json_takeout(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    entries = []
    for item in data:
        title = item.get("title", "")
        time_str = item.get("time", "")
        details = item.get("details", [])
        prompt = ""
        response = ""
        for d in details:
            if isinstance(d, dict):
                name = d.get("name", "")
                if "prompt" in name.lower():
                    prompt = d.get("value", "")
                elif "response" in name.lower():
                    response = d.get("value", "")
        if not prompt and title:
            prompt = title
        if prompt or response:
            entries.append({"time": time_str, "prompt": prompt, "response": response})
    return entries


def _parse_html_takeout(path: Path) -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed; install it to parse Gemini HTML exports")
        return []

    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "lxml")

    entries = []
    cells = soup.find_all("div", class_=re.compile(r"content-cell"))
    i = 0
    while i < len(cells):
        cell = cells[i]
        text = cell.get_text(separator="\n").strip()
        time_tag = cell.find("span", class_=re.compile(r"date"))
        time_str = time_tag.get_text().strip() if time_tag else ""
        if text:
            entries.append({"time": time_str, "prompt": text, "response": ""})
        i += 1
    return entries


class GeminiParser:
    name = "gemini"

    def detect(self, path: Path) -> bool:
        name = path.name.lower()
        if name == "myactivity.json":
            return True
        if name == "myactivity.html":
            return True
        if path.suffix == ".json":
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, list) and data and "title" in data[0] and "time" in data[0]:
                    return True
            except Exception:
                pass
        return False

    def parse(self, path: Path) -> Iterator[dict]:
        if path.suffix.lower() == ".html":
            entries = _parse_html_takeout(path)
        else:
            entries = _parse_json_takeout(path)

        if not entries:
            logger.warning("No entries parsed from Gemini export: %s", path)
            return

        sessions = _group_into_sessions(entries)
        for idx, session in enumerate(sessions):
            turns = []
            for entry in session:
                if entry.get("prompt"):
                    turns.append({"role": "user", "content": entry["prompt"],
                                  "timestamp": entry.get("time")})
                if entry.get("response"):
                    turns.append({"role": "assistant", "content": entry["response"],
                                  "timestamp": entry.get("time")})

            if not turns:
                continue

            first_ts = session[0].get("time", "")
            title = (session[0].get("prompt") or "Gemini conversation")[:60]
            session_id = f"gemini-{idx}-{first_ts}"

            yield convert_to_schema(
                source="gemini",
                source_id=session_id,
                title=title,
                turns=turns,
                created_at=first_ts or None,
                extra_metadata={
                    "grouping_confidence": "medium",
                    "session_index": idx,
                    "entry_count": len(session),
                },
            )
