"""``cheap pretooluse-hook`` — Claude Code PreToolUse:Read interceptor.

Reads the PreToolUse JSON contract from stdin, decides whether the
about-to-fire ``Read`` is delegate-worthy, and writes a structured
response on stdout.

Decision shape (always ``permissionDecision: "allow"`` — we nudge,
not block):

    {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "<text the USER sees>",
        "additionalContext": "<text the AGENT sees, only on nudge>"
    }}

Skip rules (no nudge):
  - file_path matches binary/image/PDF/video extension
  - file_path matches secrets-guard pattern (auth/crypto/.env/.key/etc)
  - tool_input has ``offset`` or ``limit`` (line-targeted read)
  - file is < SHORT_FILE_LINES lines (single Read fully closes it)
  - last few tool_uses include Edit/Write on the same path
    (Edit-follows-Read pattern, legitimate exception)

Trigger rules (emit nudge):
  - "multi-file" — ≥ MULTI_READ_THRESHOLD recent full-file Reads in
    the last MULTI_READ_WINDOW tool_uses → strongest nudge
  - "large-file" — single Read of file ≥ LARGE_FILE_LINES lines →
    softer nudge

Decisions are also appended to ``~/.cache/cheap-llm/hook.log`` for
later effectiveness analysis (one JSON line per Read seen).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# --- thresholds (tunable via env) -------------------------------------------

SHORT_FILE_LINES = int(os.environ.get("CHEAP_HOOK_SHORT_LINES", "100"))
LARGE_FILE_LINES = int(os.environ.get("CHEAP_HOOK_LARGE_LINES", "200"))
MULTI_READ_THRESHOLD = int(os.environ.get("CHEAP_HOOK_MULTI_THRESHOLD", "2"))
MULTI_READ_WINDOW = int(os.environ.get("CHEAP_HOOK_MULTI_WINDOW", "5"))
TRANSCRIPT_TAIL_BYTES = 64 * 1024  # last 64 KiB of jsonl is plenty

_BINARY_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg",
    ".pdf", ".mp4", ".mov", ".webm", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
)
_SECRETS_HINTS = (
    "auth", "crypto", "secret", "credential",
    ".env", ".key", ".pem", ".pfx", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", ".npmrc", ".pypirc",
)


# --- core decision logic -----------------------------------------------------

def _is_binary_path(path: str) -> bool:
    p = path.lower()
    return p.endswith(_BINARY_EXTS)


def _is_secrets_path(path: str) -> bool:
    p = path.lower()
    return any(h in p for h in _SECRETS_HINTS)


def _file_line_count(path: str) -> int | None:
    """Cheap line count; returns None on error (file vanished, binary)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        # Heuristic: if many NULs, it's binary; treat as 0 (skip).
        if data.count(b"\x00") > 8:
            return 0
        return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
    except OSError:
        return None


def _read_recent_tool_uses(transcript_path: str, n: int = 20) -> list[dict]:
    """Tail-read the session JSONL and return the last `n` tool_use records.

    Each record is ``{"name": str, "input": dict, "ts": str}``. Errors
    swallowed — hook must never fail on a malformed transcript line.
    """
    out: list[dict] = []
    try:
        size = os.path.getsize(transcript_path)
        offset = max(0, size - TRANSCRIPT_TAIL_BYTES)
        with open(transcript_path, "rb") as f:
            f.seek(offset)
            tail = f.read().decode("utf-8", errors="ignore")
        # Drop possibly truncated first line.
        lines = tail.splitlines()
        if offset > 0 and lines:
            lines = lines[1:]
        for line in lines:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "assistant":
                continue
            content = ev.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            ts = ev.get("timestamp", "")
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    out.append({
                        "name": block.get("name", ""),
                        "input": block.get("input", {}) or {},
                        "ts": ts,
                    })
    except OSError:
        pass
    return out[-n:]


def _recent_edit_on_same_file(
    file_path: str, recent: list[dict], window: int = 5
) -> bool:
    """True if any of the last `window` tool_uses was Edit/Write/MultiEdit
    on the same file. Catches the legitimate Read-then-Edit pattern."""
    edit_tools = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
    for tu in recent[-window:]:
        if tu["name"] not in edit_tools:
            continue
        if tu["input"].get("file_path") == file_path:
            return True
    return False


def _recent_full_reads(recent: list[dict], window: int) -> int:
    """Count how many of the last `window` tool_uses were full-file Reads."""
    n = 0
    for tu in recent[-window:]:
        if tu["name"] != "Read":
            continue
        inp = tu["input"]
        if inp.get("offset") is None and inp.get("limit") is None:
            n += 1
    return n


def decide(payload: dict) -> tuple[str, str, str]:
    """Return ``(skip_reason, user_msg, agent_msg)``.

    If ``skip_reason`` is non-empty the call is correctly native-Read
    territory and we emit no nudge. Otherwise ``user_msg`` and
    ``agent_msg`` carry the nudge text.
    """
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    offset = tool_input.get("offset")
    limit = tool_input.get("limit")

    if not file_path:
        return "no-file-path", "", ""
    if _is_binary_path(file_path):
        return "binary-or-image", "", ""
    if _is_secrets_path(file_path):
        return "secrets-pattern", "", ""
    if offset is not None or limit is not None:
        return "line-targeted", "", ""

    n_lines = _file_line_count(file_path)
    if n_lines is None:
        return "file-unreadable", "", ""
    if n_lines == 0:
        return "binary-content", "", ""
    if n_lines < SHORT_FILE_LINES:
        return "short-file", "", ""

    transcript_path = payload.get("transcript_path", "")
    recent = (
        _read_recent_tool_uses(transcript_path)
        if transcript_path
        else []
    )

    if _recent_edit_on_same_file(file_path, recent):
        return "recent-edit-same-file", "", ""

    n_recent_reads = _recent_full_reads(recent, MULTI_READ_WINDOW)
    if n_recent_reads >= MULTI_READ_THRESHOLD:
        # Strong nudge — multi-file pattern is the biggest win.
        return (
            "",
            (
                f"💡 Multi-file pattern: {n_recent_reads + 1} full reads in "
                f"the last {MULTI_READ_WINDOW} tool calls. Consider "
                f"`cheap read F1 F2 ... -q '<question>'` for ~10× compression."
            ),
            (
                f"DELEGATION HINT — you have made {n_recent_reads + 1} full-"
                f"file Reads in the last {MULTI_READ_WINDOW} turns. This is "
                f"the strongest delegate-worthy pattern. STOP and run "
                f"`cheap read <files...> -q '<your question>'` instead. "
                f"You will get a ~600-token markdown summary covering all "
                f"files at once, costing ~$0.002 vs ~10k tokens of your "
                f"context. Exception: if you need exact line citations or "
                f"will Edit one of these files next, native Read is correct."
            ),
        )

    if n_lines >= LARGE_FILE_LINES:
        return (
            "",
            (
                f"💡 Large file ({n_lines} lines, ~{n_lines * 8} input "
                f"tokens). Consider `cheap read {Path(file_path).name} "
                f"-q '<question>'` if you don't need line citations."
            ),
            (
                f"DELEGATION HINT — about to read {n_lines}-line file "
                f"({file_path}). Exceptions where native Read is correct: "
                f"(a) next tool call is Edit/Write on this file, "
                f"(b) you need line-number citations, "
                f"(c) security review needing exact bytes. "
                f"Otherwise: `cheap read {file_path} -q '<question>'` "
                f"returns ~600-token summary at ~10× compression."
            ),
        )

    return "below-thresholds", "", ""


# --- IO --------------------------------------------------------------------

def _hook_log_path() -> Path:
    base = Path(
        os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    )
    p = base / "cheap-llm" / "hook.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _log_decision(payload: dict, skip_reason: str, nudged: bool) -> None:
    try:
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session": payload.get("session_id", "")[:8],
            "file": payload.get("tool_input", {}).get("file_path", ""),
            "skip": skip_reason or None,
            "nudged": nudged,
        }, separators=(",", ":"))
        with open(_hook_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # never break the hook on log failure


def _emit_allow(reason: str = "", agent_ctx: str = "") -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if reason:
        out["hookSpecificOutput"]["permissionDecisionReason"] = reason
    if agent_ctx:
        out["hookSpecificOutput"]["additionalContext"] = agent_ctx
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Entry point invoked by Claude Code via ``cheap pretooluse-hook``.

    Always exits 0. Never blocks. Worst-case (malformed input, exception)
    we emit a bare ``allow`` so the agent's Read proceeds unaffected.
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        _emit_allow()
        return 0

    try:
        skip_reason, user_msg, agent_msg = decide(payload)
    except Exception:  # noqa: BLE001 — hook must NEVER crash
        _emit_allow()
        return 0

    nudged = bool(user_msg or agent_msg)
    _log_decision(payload, skip_reason, nudged)
    _emit_allow(reason=user_msg, agent_ctx=agent_msg)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
