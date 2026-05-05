"""Append-only JSON-line usage log.

One line per `cheap read` / `cheap extract` invocation, written to
``~/.cache/cheap-llm/usage.log`` (or ``$XDG_CACHE_HOME/cheap-llm/usage.log``).

The log is observability, not the critical path: any I/O failure
(no perms, disk full, parent dir not writable, ...) is swallowed.
The user's `read` / `extract` call must never fail because the log
could not be appended.

Schema (one JSON object per line, all keys optional except ``ts``,
``cmd``, ``model``, ``input_chars``, ``output_tokens``, ``elapsed_ms``):

    {
      "ts":              "2026-05-05T13:02:11Z",       # UTC ISO 8601
      "cmd":             "read" | "extract",
      "model":           "deepseek/deepseek-chat-v3-0324",
      "input_chars":     15823,
      "output_tokens":   587,
      "elapsed_ms":      2143,
      "files":           3,                             # read only
      "n_messages":      8,                             # extract only
      "backend":         "claude" | "codex" | "explicit"  # extract only
    }

Reading the log later:

    tail -100 "$(cheap usage path)" | jq .

…or any other JSON-line tool. We deliberately do not bake a reporting
command yet — first collect a real week of data, then decide what
report shape is actually useful.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_path() -> Path:
    """Resolve the usage-log path. Honours $XDG_CACHE_HOME."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "cheap-llm" / "usage.log"


def record(
    *,
    cmd: str,
    model: str,
    input_chars: int,
    output_tokens: int,
    elapsed_ms: int,
    path: Path | None = None,
    **extra: Any,
) -> None:
    """Append one entry to the usage log. Best-effort — never raises.

    `extra` carries cmd-specific fields (``files`` for read,
    ``n_messages`` + ``backend`` for extract). They are merged into
    the JSON object as-is, with one rule: keys whose value is ``None``
    are dropped so the log stays compact.
    """
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cmd": cmd,
        "model": model,
        "input_chars": input_chars,
        "output_tokens": output_tokens,
        "elapsed_ms": elapsed_ms,
    }
    for k, v in extra.items():
        if v is None:
            continue
        entry[k] = v

    target = path or log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        with target.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        # Best-effort: the user's read/extract call must not fail because
        # the log file is unwritable. Surface a single stderr warning so
        # the user can investigate if it matters.
        print(
            f"cheap: warning — could not append to usage log {target}: {e}",
            file=sys.stderr,
        )


__all__ = ["log_path", "record"]
