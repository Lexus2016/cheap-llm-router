"""Parser for Claude Code session JSONL.

Layout: ``~/.claude/projects/<slug>/<uuid>.jsonl``. Each line is a JSON
record with at least ``sessionId``, ``type``, and (for chat turns)
``message`` with ``role`` and ``content``. ``content`` is either a
plain string (older records) or a list of typed parts:
``{type:"text",text:...}``, ``{type:"tool_use",id,name,input}``,
``{type:"tool_result",tool_use_id,content}``.

This parser yields a normalised ``Message`` per textual turn / tool
event; it does not try to preserve every metadata field.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from . import Message, Role


def parse(path: Path) -> Iterator[Message]:
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                # Skip malformed lines rather than aborting — partial
                # transcripts during live sessions are normal.
                continue
            yield from _records(rec)


def _records(rec: dict) -> Iterator[Message]:
    rec_type = rec.get("type")
    ts = rec.get("timestamp")
    msg = rec.get("message")

    # Chat turn: rec.type in {"user","assistant"} carries a `message`.
    if rec_type in ("user", "assistant") and isinstance(msg, dict):
        role = Role.USER if msg.get("role") == "user" else Role.ASSISTANT
        content = msg.get("content")

        if isinstance(content, str):
            yield Message(role=role, text=content, timestamp=ts)
            return

        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    yield Message(role=role, text=part.get("text", ""), timestamp=ts)
                elif ptype == "tool_use":
                    name = part.get("name", "")
                    input_repr = json.dumps(part.get("input", {}), separators=(",", ":"))
                    yield Message(
                        role=Role.TOOL_USE,
                        text=input_repr,
                        tool_name=name,
                        timestamp=ts,
                    )
                elif ptype == "tool_result":
                    inner = part.get("content")
                    text = inner if isinstance(inner, str) else json.dumps(inner)
                    yield Message(
                        role=Role.TOOL_RESULT,
                        text=text,
                        timestamp=ts,
                    )
        return

    # Non-chat record types (summary, attachment, permission-mode, ...)
    # surface as META so callers can decide whether to drop them.
    if rec_type:
        text = rec.get("summary") or rec.get("text") or ""
        yield Message(role=Role.META, text=str(text), timestamp=ts)
