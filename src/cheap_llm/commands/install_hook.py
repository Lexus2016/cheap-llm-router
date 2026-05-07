"""``cheap install-hook`` — register the PreToolUse:Read hook in Claude Code.

Adds a ``hooks.PreToolUse`` entry with ``matcher: "Read"`` and
``command: "cheap pretooluse-hook"`` to ``~/.claude/settings.json``.
Idempotent: skips if an entry pointing at the same command already
exists. With ``--force`` rewrites the existing entry (in case the
shipped command name or args change).

Other agents (Codex CLI, Cursor, Aider, Cline, Continue, OpenCode,
Gemini CLI) currently have no equivalent PreToolUse hook surface.
For those, the rule installed by ``cheap install-rule`` remains the
only delegation mechanism — see release notes / README for details.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_GENERIC_ERROR = 1


_HOOK_COMMAND = "cheap pretooluse-hook"
_HOOK_MATCHER = "Read"


def _settings_path(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def _load_settings(path: Path) -> dict:
    """Return parsed settings.json, or {} if absent. Raises on malformed JSON."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else {}


def _has_our_hook(entries: list[dict]) -> int | None:
    """Return the index of an existing entry that points at our command,
    or None if none found. Recognised by ANY hook within the entry whose
    ``command`` substring contains 'pretooluse-hook' (so renames between
    versions still match)."""
    for i, entry in enumerate(entries):
        if entry.get("matcher") != _HOOK_MATCHER:
            continue
        for h in entry.get("hooks", []) or []:
            cmd = (h.get("command") or "")
            if "pretooluse-hook" in cmd:
                return i
    return None


def _build_entry() -> dict:
    return {
        "matcher": _HOOK_MATCHER,
        "hooks": [{"type": "command", "command": _HOOK_COMMAND}],
    }


def install_into(settings_path: Path, *, force: bool) -> str:
    """Write the hook entry into `settings_path`. Returns a one-line action.

    Idempotent without `force`; with `force` rewrites our entry in place.
    Other entries (other matchers, other events) are preserved verbatim.
    """
    try:
        settings = _load_settings(settings_path)
    except json.JSONDecodeError as e:
        return (
            f"error: {settings_path} is not valid JSON ({e}). "
            "Fix it manually or back it up before re-running."
        )

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return f"error: hooks key in {settings_path} is not an object"

    pre = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre, list):
        return f"error: hooks.PreToolUse in {settings_path} is not a list"

    idx = _has_our_hook(pre)
    if idx is not None and not force:
        return f"already installed in {settings_path} (PreToolUse:Read)"

    new_entry = _build_entry()
    if idx is not None:
        pre[idx] = new_entry
        msg = f"installed: replaced PreToolUse:Read entry in {settings_path} (--force)"
    else:
        pre.append(new_entry)
        msg = f"installed: added PreToolUse:Read entry to {settings_path}"

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )
    return msg


def run(*, force: bool = False, home: Path | None = None) -> int:
    home = home or Path.home()
    path = _settings_path(home)
    msg = install_into(path, force=force)
    if msg.startswith("error:"):
        print(f"cheap install-hook: {msg}", file=sys.stderr)
        return EXIT_GENERIC_ERROR
    print(msg, file=sys.stderr)
    if not (path.parent / "settings.json").exists():
        # Belt-and-braces: write succeeded but somehow file is gone? Shouldn't
        # happen, but surface the discrepancy if it does.
        print(
            f"cheap install-hook: WARNING {path} not found after write",
            file=sys.stderr,
        )
    return EXIT_OK


__all__ = [
    "EXIT_OK",
    "EXIT_GENERIC_ERROR",
    "install_into",
    "run",
]
