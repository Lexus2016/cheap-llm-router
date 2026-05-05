"""Fallback parser: feed file contents as one giant Role.OTHER blob.

Used when ``detect_format`` cannot match a known format. Lets the
caller still attempt a summary on an unrecognised JSONL or plain-text
transcript, with the understanding that quality will be lower.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from . import Message, Role


def parse(path: Path) -> Iterator[Message]:
    text = path.read_text(encoding="utf-8", errors="replace")
    yield Message(role=Role.OTHER, text=text)
