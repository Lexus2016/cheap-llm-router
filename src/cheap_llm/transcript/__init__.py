"""Pluggable transcript parsers.

Each agent CLI (Claude Code, OpenAI Codex CLI, ...) persists session
history in its own JSONL format. This package provides a thin parser
per format and a `detect_format` shim that auto-picks the right one
from the first record. All parsers normalise to ``Message`` so the
``cheap extract`` command does not care about the source format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator, Sequence


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    META = "meta"
    OTHER = "other"


@dataclass(frozen=True)
class Message:
    """Format-agnostic transcript entry, ready to feed into a prompt.

    `text` carries the human-readable content (assistant text, user
    message, tool stdout, ...). `tool_name` is set only for
    ``TOOL_USE`` / ``TOOL_RESULT`` entries.
    """
    role: Role
    text: str
    tool_name: str | None = None
    timestamp: str | None = None


class Mode(str, Enum):
    """Which slice of the transcript the caller wants."""
    FULL = "full"                   # everything
    MESSAGES_ONLY = "messages-only"  # drop tool_use + tool_result


# --- format detection --------------------------------------------------------

# Each parser module exposes ``parse(path) -> Iterator[Message]``.
# Detection looks at the first non-empty JSON line and matches by shape.
ParserFn = Callable[[Path], Iterator[Message]]


def detect_format(path: Path) -> ParserFn:
    """Return the parser function appropriate for the file's format.

    Decision is based on the FIRST non-empty record's top-level keys:
    - has ``payload`` and ``type`` (Codex RolloutLine)         → codex
    - has ``sessionId`` or ``message`` (Claude Code session)   → claude
    - anything else                                            → generic
    """
    from . import claude, codex, generic

    first = _first_record(path)
    if first is None:
        return generic.parse

    keys = set(first.keys())
    if "payload" in keys and "type" in keys:
        return codex.parse
    if "sessionId" in keys or "message" in keys:
        return claude.parse
    return generic.parse


def _first_record(path: Path) -> dict | None:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                return None
            return obj if isinstance(obj, dict) else None
    return None


# --- post-processing helpers (mode + tail) -----------------------------------

def filter_mode(messages: Iterator[Message], mode: Mode) -> Iterator[Message]:
    """Apply the user-selected mode filter."""
    if mode == Mode.FULL:
        yield from messages
        return
    if mode == Mode.MESSAGES_ONLY:
        # Keep only real chat turns. Drop tool events AND meta records
        # (session_meta, summary, ItemCompleted, TokenCount, ...) — those
        # are noise for a "what did we talk about" summary.
        for m in messages:
            if m.role in (Role.TOOL_USE, Role.TOOL_RESULT, Role.META, Role.OTHER):
                continue
            yield m
        return
    # Unknown mode falls back to full (defensive; CLI validates earlier).
    yield from messages


def take_tail(messages: Sequence[Message], n: int | None) -> list[Message]:
    """Return the last `n` messages, or all if `n is None or n <= 0`."""
    if not n or n <= 0:
        return list(messages)
    return list(messages)[-n:]


def render_for_prompt(messages: Sequence[Message]) -> str:
    """Render a normalised message stream as a compact text block.

    Format:
        [ROLE] text
        [ROLE: tool_name] text
    Empty messages are skipped.
    """
    lines: list[str] = []
    for m in messages:
        if not m.text.strip() and m.role not in (Role.TOOL_USE,):
            continue
        if m.tool_name:
            lines.append(f"[{m.role.value.upper()}: {m.tool_name}] {m.text}")
        else:
            lines.append(f"[{m.role.value.upper()}] {m.text}")
    return "\n".join(lines)


__all__ = [
    "Role",
    "Message",
    "Mode",
    "detect_format",
    "filter_mode",
    "take_tail",
    "render_for_prompt",
]
