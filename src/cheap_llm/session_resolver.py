"""Resolve which session transcript belongs to *this* invocation.

Order of priority (first match wins):

1. ``--jsonl <path>``                                    — explicit file
2. ``--session-id <uuid>``                               — glob both backends
3. ``$CODEX_THREAD_ID`` env var                          — Codex deterministic
4. ``~/.cache/cheap-llm/sessions/<PPID>.txt`` exists     — Claude (hook wrote it)
5. Claude fallback by current-cwd slug + newest mtime    — sets
   ``ResolvedSession.fallback_warning`` so the caller can surface it
6. Nothing matched                                       — raise NoSessionFound

Resolver is pure: it does not write to stderr. The caller is expected
to print ``fallback_warning`` if it is non-None — keeping I/O at the
edge makes resolver trivial to unit-test without monkey-patching print.

The Claude side is heuristic in step 5 because Claude Code does not
expose a session id to child processes. Step 4 turns it deterministic
once the SessionStart hook (Commit 4) is installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


CACHE_SUBDIR = Path(".cache") / "cheap-llm" / "sessions"


class NoSessionFound(RuntimeError):
    pass


class AmbiguousSession(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedSession:
    """Output of :func:`resolve_session`."""
    path: Path
    backend: str                      # "claude" | "codex" | "explicit"
    how: str                          # human-readable trail for `--debug` / errors
    fallback_warning: str | None = None  # set when step-5 heuristic kicked in


def resolve_session(
    *,
    jsonl: str | None = None,
    session_id: str | None = None,
    home: Path | None = None,
    cwd: str | None = None,
    ppid: int | None = None,
    env: dict[str, str] | None = None,
) -> ResolvedSession:
    """Pick the right transcript file. Pure: no I/O beyond filesystem reads."""
    home = home or Path.home()
    env = env if env is not None else dict(os.environ)
    cwd = cwd or os.getcwd()
    ppid = ppid if ppid is not None else os.getppid()

    # 1. explicit --jsonl
    if jsonl:
        p = Path(jsonl).expanduser()
        if not p.exists():
            raise NoSessionFound(f"--jsonl path does not exist: {p}")
        return ResolvedSession(path=p, backend="explicit", how=f"--jsonl {p}")

    # 2. explicit --session-id: try Claude AND Codex globs.
    if session_id:
        return _resolve_by_session_id(session_id, home, env)

    # 3. CODEX_THREAD_ID set → Codex deterministic
    thread_id = env.get("CODEX_THREAD_ID")
    if thread_id:
        path = _find_codex_rollout(thread_id, home, env)
        if path:
            return ResolvedSession(
                path=path,
                backend="codex",
                how=f"$CODEX_THREAD_ID={thread_id}",
            )
        # Set but file missing — surface clearly rather than silently
        # falling through to Claude heuristics.
        raise NoSessionFound(
            f"$CODEX_THREAD_ID={thread_id} set but no rollout file matched "
            f"under {_codex_sessions_root(home, env)}"
        )

    # 4. Claude SessionStart hook wrote ~/.cache/cheap-llm/sessions/<PPID>.txt
    hook_file = home / CACHE_SUBDIR / f"{ppid}.txt"
    if hook_file.exists():
        path_str = hook_file.read_text(encoding="utf-8").strip()
        if path_str:
            p = Path(path_str)
            if p.exists():
                return ResolvedSession(
                    path=p,
                    backend="claude",
                    how=f"hook tmp-file {hook_file}",
                )

    # 5. Claude fallback: newest mtime within current-cwd slug.
    fallback = _claude_newest_in_cwd_slug(cwd, home)
    if fallback:
        warning = (
            f"no SessionStart hook output found; falling back to newest "
            f"jsonl in current-cwd slug ({fallback.name}). "
            f"Pass --session-id <uuid> to override."
        )
        return ResolvedSession(
            path=fallback,
            backend="claude",
            how=f"cwd-slug newest-mtime fallback ({cwd})",
            fallback_warning=warning,
        )

    # 6. nothing matched
    raise NoSessionFound(
        "could not resolve a session automatically. Pass --jsonl <path> "
        "or --session-id <uuid> explicitly. (Claude hook not installed? "
        "Codex CLI not running? See INSTALL.md.)"
    )


# --- helpers -----------------------------------------------------------------

def _resolve_by_session_id(
    session_id: str, home: Path, env: dict[str, str]
) -> ResolvedSession:
    claude_hits = list(_glob_claude_by_id(session_id, home))
    codex_hit = _find_codex_rollout(session_id, home, env)

    if claude_hits and codex_hit:
        raise AmbiguousSession(
            f"session id {session_id} matches both a Claude jsonl "
            f"({claude_hits[0]}) and a Codex rollout ({codex_hit}). "
            f"Disambiguate by passing --jsonl <path> directly."
        )
    if claude_hits:
        return ResolvedSession(
            path=claude_hits[0],
            backend="claude",
            how=f"--session-id {session_id}",
        )
    if codex_hit:
        return ResolvedSession(
            path=codex_hit,
            backend="codex",
            how=f"--session-id {session_id}",
        )
    raise NoSessionFound(
        f"--session-id {session_id} did not match any Claude jsonl "
        f"under {home}/.claude/projects/*/ or any Codex rollout under "
        f"{_codex_sessions_root(home, env)}/**"
    )


def _glob_claude_by_id(session_id: str, home: Path):
    root = home / ".claude" / "projects"
    if not root.exists():
        return
    yield from root.glob(f"*/{session_id}.jsonl")


def _codex_sessions_root(home: Path, env: dict[str, str]) -> Path:
    base = env.get("CODEX_HOME") or str(home / ".codex")
    return Path(base) / "sessions"


def _find_codex_rollout(thread_id: str, home: Path, env: dict[str, str]) -> Path | None:
    """Recursive glob: $CODEX_HOME/sessions/**/rollout-*-<thread_id>.jsonl"""
    root = _codex_sessions_root(home, env)
    if not root.exists():
        return None
    matches = list(root.rglob(f"rollout-*-{thread_id}.jsonl"))
    return matches[0] if matches else None


def _claude_newest_in_cwd_slug(cwd: str, home: Path) -> Path | None:
    """Return the most-recently-modified .jsonl under the slug for cwd."""
    slug = cwd.replace("/", "-")
    slug_dir = home / ".claude" / "projects" / slug
    if not slug_dir.exists():
        return None
    candidates = list(slug_dir.glob("*.jsonl"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


__all__ = [
    "NoSessionFound",
    "AmbiguousSession",
    "ResolvedSession",
    "resolve_session",
    "CACHE_SUBDIR",
]
