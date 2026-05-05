"""``cheap install-claude-rule`` — idempotent installer for the
CLAUDE.md delegation rule.

Reads the canonical snippet shipped with the package and writes it
into ``~/.claude/CLAUDE.md`` as a new section, preserving any
existing content.
"""

from __future__ import annotations

import re
import sys
from importlib.resources import files
from pathlib import Path

EXIT_OK = 0
EXIT_GENERIC_ERROR = 1

_HEADING = "## Cheap LLM delegation"
_HEADING_RE = re.compile(rf"^{re.escape(_HEADING)}\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)


def _claude_md_path() -> Path:
    return Path.home() / ".claude" / "CLAUDE.md"


def _load_snippet() -> str:
    """Read the snippet shipped in cheap_llm/_data/."""
    resource = files("cheap_llm").joinpath("_data/claude_md_snippet.md")
    return resource.read_text(encoding="utf-8").rstrip() + "\n"


def _find_block_bounds(text: str) -> tuple[int, int] | None:
    """Return (start, end) of the existing block, or None if absent.

    Block runs from the line of ``## Cheap LLM delegation`` up to (but
    excluding) the next ``## `` heading, or to EOF if last section.
    """
    m = _HEADING_RE.search(text)
    if not m:
        return None
    start = m.start()
    rest = text[m.end():]
    nm = _NEXT_HEADING_RE.search(rest)
    end = m.end() + nm.start() if nm else len(text)
    return start, end


def run(force: bool = False, target: Path | None = None) -> int:
    target = target or _claude_md_path()
    snippet = _load_snippet()

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(snippet, encoding="utf-8")
        print(f"installed: created {target}", file=sys.stderr)
        return EXIT_OK

    text = target.read_text(encoding="utf-8")
    bounds = _find_block_bounds(text)

    if bounds is None:
        # Append with one blank line separator.
        sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        new_text = text + sep + snippet
        target.write_text(new_text, encoding="utf-8")
        print(f"installed: appended section to {target}", file=sys.stderr)
        return EXIT_OK

    if not force:
        print(f"already installed at {target}", file=sys.stderr)
        return EXIT_OK

    start, end = bounds
    new_text = text[:start] + snippet + text[end:]
    target.write_text(new_text, encoding="utf-8")
    print(f"installed: replaced section in {target} (--force)", file=sys.stderr)
    return EXIT_OK
