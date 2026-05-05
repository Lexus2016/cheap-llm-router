"""``cheap install-claude-rule`` — kept as a deprecated alias.

Forwards to :mod:`cheap_llm.commands.install_rule` with target=``claude``,
so existing scripts and Phase-1-era tests keep working without change.

Prefer ``cheap install-rule`` for new code — it can target Claude Code,
OpenAI Codex CLI's ``AGENTS.md``, or both.
"""

from __future__ import annotations

from pathlib import Path

from . import install_rule as _impl


# Re-export the constants the original module published, so callers
# importing them keep compiling.
EXIT_OK = _impl.EXIT_OK
EXIT_GENERIC_ERROR = _impl.EXIT_GENERIC_ERROR


def run(force: bool = False, target: Path | None = None) -> int:
    """Install the rule into ``~/.claude/CLAUDE.md`` (or `target` if given)."""
    if target is not None:
        return _impl.run(force=force, targets_override=[target])
    return _impl.run(target="claude", force=force)
