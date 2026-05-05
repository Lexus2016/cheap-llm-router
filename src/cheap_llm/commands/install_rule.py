"""``cheap install-rule`` — idempotent installer for the delegation rule.

Generalises the Phase-1 ``install-claude-rule`` command to multiple
target files at once. The same dense snippet
(``cheap_llm/_data/claude_md_snippet.md``) is written into every
selected target.

Targets:
    - ``claude`` → ``~/.claude/CLAUDE.md``     (Claude Code)
    - ``codex``  → ``~/.codex/AGENTS.md``       (OpenAI Codex CLI)
    - ``all``    → both, regardless of presence
    - ``auto``   (default) → only the targets whose parent dir
      already exists. If neither dir exists, falls back to creating
      ``~/.claude/CLAUDE.md`` so the command always does *something*
      useful on a fresh machine.

The block is recognised by any ``## Cheap LLM …`` heading
(case-insensitive), so re-running on a CLAUDE.md installed by an
older version of this package stays idempotent and ``--force``
correctly replaces it in place.
"""

from __future__ import annotations

import re
import sys
from importlib.resources import files
from pathlib import Path
from typing import Sequence


EXIT_OK = 0
EXIT_GENERIC_ERROR = 1


_HEADING_PREFIX = "## Cheap LLM"
_HEADING_RE = re.compile(
    rf"^{re.escape(_HEADING_PREFIX)}\b.*$",
    re.MULTILINE | re.IGNORECASE,
)
_NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)
_VERSION_RE = re.compile(r"<!--\s*cheap-llm-rule\s+v=(\d+)\s*-->")


# --- target resolution -------------------------------------------------------

VALID_TARGETS = ("claude", "codex", "all", "auto")


def _claude_md_path(home: Path) -> Path:
    return home / ".claude" / "CLAUDE.md"


def _codex_agents_path(home: Path) -> Path:
    return home / ".codex" / "AGENTS.md"


def resolve_targets(
    target: str, home: Path | None = None
) -> list[Path]:
    """Map a `--target` value to the list of paths to write into.

    Pure: filesystem is touched only for `auto` mode (and only `Path.exists`).
    """
    home = home or Path.home()
    if target not in VALID_TARGETS:
        raise ValueError(
            f"invalid --target {target!r}; pick one of: {', '.join(VALID_TARGETS)}"
        )

    if target == "claude":
        return [_claude_md_path(home)]
    if target == "codex":
        return [_codex_agents_path(home)]
    if target == "all":
        return [_claude_md_path(home), _codex_agents_path(home)]

    # auto: detect which agents are installed; install into the ones present.
    out: list[Path] = []
    if (home / ".claude").exists():
        out.append(_claude_md_path(home))
    if (home / ".codex").exists():
        out.append(_codex_agents_path(home))
    if not out:
        # Nothing detected — be useful and bootstrap the Claude side, since
        # that's still by far the most common consumer.
        out.append(_claude_md_path(home))
    return out


# --- snippet IO --------------------------------------------------------------

def _load_snippet() -> str:
    """Read the canonical snippet shipped in cheap_llm/_data/."""
    resource = files("cheap_llm").joinpath("_data/claude_md_snippet.md")
    return resource.read_text(encoding="utf-8").rstrip() + "\n"


# --- block manipulation ------------------------------------------------------

def _find_block_bounds(text: str) -> tuple[int, int] | None:
    """Return (start, end) of the existing block, or None if absent.

    Block runs from the matched ``## Cheap LLM …`` heading line up to
    (but excluding) the next ``## `` heading, or EOF if last section.
    """
    m = _HEADING_RE.search(text)
    if not m:
        return None
    start = m.start()
    rest = text[m.end():]
    nm = _NEXT_HEADING_RE.search(rest)
    end = m.end() + nm.start() if nm else len(text)
    return start, end


def _parse_version(text: str) -> int:
    """Return rule version embedded in `text`, or 1 if no marker found.

    A missing marker means the block was installed by an old release that
    pre-dates versioning. Treat those as v1 — they were the first stable
    rule shape, and bumping shipped to v2+ will then surface the
    upgrade hint correctly.
    """
    m = _VERSION_RE.search(text)
    return int(m.group(1)) if m else 1


def install_into(target: Path, *, force: bool, snippet: str) -> str:
    """Write `snippet` into `target`. Returns a one-line action description.

    Idempotent without `force`; with `force` replaces the existing block.
    Without `force`, if the installed block has an older rule version than
    the shipped snippet, surfaces an upgrade hint so the user can decide
    whether to overwrite (since `--force` discards any local edits, e.g.
    their own ``Past mistakes`` entries).
    """
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(snippet, encoding="utf-8")
        return f"installed: created {target}"

    text = target.read_text(encoding="utf-8")
    bounds = _find_block_bounds(text)

    if bounds is None:
        sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        target.write_text(text + sep + snippet, encoding="utf-8")
        return f"installed: appended section to {target}"

    if not force:
        start, end = bounds
        installed_v = _parse_version(text[start:end])
        shipped_v = _parse_version(snippet)
        if shipped_v > installed_v:
            return (
                f"already installed at {target} (rule v{installed_v}; "
                f"v{shipped_v} available — run with --force to upgrade, "
                f"this REPLACES the block including any local edits)"
            )
        return f"already installed at {target} (rule v{installed_v})"

    start, end = bounds
    trailing = text[end:]
    separator = "\n" if trailing.startswith("##") else ""
    new_text = text[:start] + snippet + separator + trailing
    target.write_text(new_text, encoding="utf-8")
    return f"installed: replaced section in {target} (--force)"


# --- public API --------------------------------------------------------------

def run(
    *,
    target: str = "auto",
    force: bool = False,
    home: Path | None = None,
    targets_override: Sequence[Path] | None = None,
) -> int:
    """Install the delegation rule into the selected targets.

    `targets_override` is for tests — bypasses target string resolution
    and writes into exactly the given paths.
    """
    try:
        targets = (
            list(targets_override)
            if targets_override is not None
            else resolve_targets(target, home=home)
        )
    except ValueError as e:
        print(f"cheap install-rule: error: {e}", file=sys.stderr)
        return EXIT_GENERIC_ERROR

    snippet = _load_snippet()
    for path in targets:
        msg = install_into(path, force=force, snippet=snippet)
        print(msg, file=sys.stderr)
    return EXIT_OK


__all__ = [
    "EXIT_OK",
    "EXIT_GENERIC_ERROR",
    "VALID_TARGETS",
    "resolve_targets",
    "install_into",
    "run",
]
