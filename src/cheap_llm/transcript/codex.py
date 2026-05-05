"""Parser for OpenAI Codex CLI rollout JSONL.

Layout: ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<thread_id>.jsonl``.
Each line is a ``RolloutLine``: ``{"timestamp":..., "type":..., "payload":...}``.

Variants of ``type`` we care about:
- ``session_meta``     → emitted as Role.META.
- ``response_item``    → assistant text / function_call (tool_use).
- ``event_msg``        → ``UserMessage`` (user turn) or ``ItemCompleted``
                         (tool result). Other events (TokenCount,
                         TurnStarted, …) surface as META.
- ``compacted``        → META marker.
- ``turn_context``     → META marker.

Reference: github.com/openai/codex codex-rs/protocol/src/protocol.rs
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
                continue
            yield from _records(rec)


def _records(rec: dict) -> Iterator[Message]:
    rec_type = rec.get("type")
    ts = rec.get("timestamp")
    payload = rec.get("payload") or {}
    if not isinstance(payload, dict):
        return

    if rec_type == "session_meta":
        cwd = payload.get("cwd", "")
        yield Message(role=Role.META, text=f"session_meta cwd={cwd}", timestamp=ts)
        return

    if rec_type == "response_item":
        role_str = payload.get("role")
        role = Role.ASSISTANT if role_str == "assistant" else Role.OTHER
        content = payload.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype in ("output_text", "text"):
                    yield Message(role=role, text=part.get("text", ""), timestamp=ts)
                elif ptype == "function_call":
                    name = part.get("name", "")
                    args_repr = json.dumps(part.get("arguments", {}), separators=(",", ":"))
                    yield Message(
                        role=Role.TOOL_USE,
                        text=args_repr,
                        tool_name=name,
                        timestamp=ts,
                    )
        elif isinstance(content, str):
            yield Message(role=role, text=content, timestamp=ts)
        return

    if rec_type == "event_msg":
        evt = payload.get("type")
        if evt == "UserMessage":
            yield Message(
                role=Role.USER,
                text=str(payload.get("message", "")),
                timestamp=ts,
            )
        elif evt == "ItemCompleted":
            yield Message(
                role=Role.TOOL_RESULT,
                text=str(payload.get("output", "")),
                timestamp=ts,
            )
        else:
            # TokenCount, TurnStarted, TurnComplete, AgentMessage, etc.
            yield Message(role=Role.META, text=f"event_msg {evt}", timestamp=ts)
        return

    if rec_type in ("compacted", "turn_context"):
        yield Message(role=Role.META, text=f"{rec_type}", timestamp=ts)
