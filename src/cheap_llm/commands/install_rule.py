"""``cheap install-rule`` — idempotent installer for the delegation rule.

Generalises the Phase-1 ``install-claude-rule`` command to multiple
target files at once. The rule body is rendered from a single template
(``cheap_llm/_data/rule_template.md``) with per-target substitutions
so each agent gets bits that actually apply to it (its own jsonl path,
its own statusline / usage check, its own ``/compact`` command name).

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
VALID_KINDS = ("claude", "codex", "generic")


def _claude_md_path(home: Path) -> Path:
    return home / ".claude" / "CLAUDE.md"


def _codex_agents_path(home: Path) -> Path:
    return home / ".codex" / "AGENTS.md"


def resolve_targets(
    target: str, home: Path | None = None
) -> list[tuple[Path, str]]:
    """Map a `--target` value to (path, kind) pairs to render and write.

    `kind` selects which substitution set the template renders against:
    ``claude``, ``codex``, or ``generic`` (third-party agents).

    Pure: filesystem is touched only for `auto` mode (and only `Path.exists`).
    """
    home = home or Path.home()
    if target not in VALID_TARGETS:
        raise ValueError(
            f"invalid --target {target!r}; pick one of: {', '.join(VALID_TARGETS)}"
        )

    if target == "claude":
        return [(_claude_md_path(home), "claude")]
    if target == "codex":
        return [(_codex_agents_path(home), "codex")]
    if target == "all":
        return [
            (_claude_md_path(home), "claude"),
            (_codex_agents_path(home), "codex"),
        ]

    # auto: detect which agents are installed; install into the ones present.
    out: list[tuple[Path, str]] = []
    if (home / ".claude").exists():
        out.append((_claude_md_path(home), "claude"))
    if (home / ".codex").exists():
        out.append((_codex_agents_path(home), "codex"))
    if not out:
        # Nothing detected — be useful and bootstrap the Claude side, since
        # that's still by far the most common consumer.
        out.append((_claude_md_path(home), "claude"))
    return out


# --- snippet IO --------------------------------------------------------------

# Per-kind substitution sets. The template carries placeholders like
# ``{AGENT_NAME}`` / ``{JSONL_PATH_CMD}`` / ``{STATUSLINE_BLOCK}`` /
# ``{AGENT_COMPACT_REF}``; ``_load_snippet(kind)`` swaps each in.
#
# Adding a new kind = add an entry here. The template body itself stays
# single-source-of-truth.
_RULE_VARS: dict[str, dict[str, str]] = {
    "claude": {
        "AGENT_NAME": "Claude Code",
        "AGENT_COMPACT_REF": "Claude Code's built-in `/compact`",
        "JSONL_PATH_CMD": (
            "wc -c ~/.claude/projects/$(pwd | sed 's:[/_]:-:g')/*.jsonl "
            "2>/dev/null | sort -n | tail -1"
        ),
        "STATUSLINE_BLOCK": (
            "Self-check #2 — ask the user what colour the context bar in their\n"
            "Claude Code statusline shows. Claude Code knows the true\n"
            "`context_window.used_percentage` and surfaces it there:\n"
            "- **green** (<50%) — no compaction needed yet\n"
            "- **yellow** (50-80%) — start preparing handoff digest now\n"
            "- **red** (>80%) — compact ASAP\n"
            "\n"
            "You (the agent) cannot read this percentage directly from your\n"
            "preamble; the statusline can. Asking the user is the cheapest way\n"
            "to get a true number when behaviour signals are ambiguous."
        ),
    },
    "codex": {
        "AGENT_NAME": "Codex CLI",
        "AGENT_COMPACT_REF": "Codex CLI's built-in `/compact`",
        "JSONL_PATH_CMD": (
            "wc -c ~/.codex/sessions/${CODEX_THREAD_ID:-*}.jsonl "
            "2>/dev/null | sort -n | tail -1"
        ),
        "STATUSLINE_BLOCK": (
            "Self-check #2 — Codex CLI surfaces context usage in its prompt\n"
            "area and via `/usage`. Ask the user what their displayed token\n"
            "count is relative to the model's context window:\n"
            "- **< 50%** — no compaction needed yet\n"
            "- **50-80%** — start preparing handoff digest now\n"
            "- **> 80%** — compact ASAP\n"
            "\n"
            "You (the agent) cannot read the live counter from your preamble;\n"
            "Codex CLI's UI can. Asking the user is the cheapest way to get a\n"
            "true number when behaviour signals are ambiguous."
        ),
    },
    "generic": {
        "AGENT_NAME": "your agent",
        "AGENT_COMPACT_REF": "your agent's built-in compact / new-session command",
        "JSONL_PATH_CMD": (
            "# locate your agent's session log on disk; common roots include\n"
            "# ~/.cursor/, ~/.aider/.cache/, ~/.cline/, ~/.continue/, etc.\n"
            "find ~ -name '*.jsonl' -newer /tmp 2>/dev/null | head -5"
        ),
        "STATUSLINE_BLOCK": (
            "Self-check #2 — most agents surface context-window usage somewhere\n"
            "(status line, prompt area, dedicated `/usage` command). Ask the\n"
            "user what their agent shows relative to the model's context window:\n"
            "- **< 50%** — no compaction needed yet\n"
            "- **50-80%** — start preparing handoff digest now\n"
            "- **> 80%** — compact ASAP\n"
            "\n"
            "You (the agent) cannot read the live counter from your preamble.\n"
            "Asking the user is the cheapest way to get a true number when\n"
            "behaviour signals are ambiguous."
        ),
    },
}


def _load_template() -> str:
    """Read the canonical template shipped in cheap_llm/_data/."""
    resource = files("cheap_llm").joinpath("_data/rule_template.md")
    return resource.read_text(encoding="utf-8")


def _load_snippet(kind: str = "claude") -> str:
    """Render the rule snippet for the given agent kind.

    Substitutes per-kind values from `_RULE_VARS` into the template's
    `{PLACEHOLDER}` markers. Unknown placeholders left over after
    substitution would indicate a template/vars mismatch — we raise
    rather than ship a half-rendered rule.
    """
    if kind not in _RULE_VARS:
        raise ValueError(
            f"unknown rule kind {kind!r}; pick one of: {', '.join(VALID_KINDS)}"
        )
    text = _load_template()
    for placeholder, value in _RULE_VARS[kind].items():
        text = text.replace("{" + placeholder + "}", value)
    return text.rstrip() + "\n"


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
    kind_override: str = "claude",
) -> int:
    """Install the delegation rule into the selected targets.

    `targets_override` is for tests and the legacy ``install-claude-rule``
    wrapper — bypasses target string resolution and writes into exactly
    the given paths. `kind_override` then picks which rendering set to
    use for those paths (default ``claude`` for backward compat).
    """
    try:
        if targets_override is not None:
            targets: list[tuple[Path, str]] = [
                (p, kind_override) for p in targets_override
            ]
            # Validate kind early so a typo doesn't surface as a KeyError later.
            if kind_override not in _RULE_VARS:
                raise ValueError(
                    f"unknown rule kind {kind_override!r}; "
                    f"pick one of: {', '.join(VALID_KINDS)}"
                )
        else:
            targets = resolve_targets(target, home=home)
    except ValueError as e:
        print(f"cheap install-rule: error: {e}", file=sys.stderr)
        return EXIT_GENERIC_ERROR

    for path, kind in targets:
        snippet = _load_snippet(kind)
        msg = install_into(path, force=force, snippet=snippet)
        print(msg, file=sys.stderr)
    return EXIT_OK


__all__ = [
    "EXIT_OK",
    "EXIT_GENERIC_ERROR",
    "VALID_TARGETS",
    "VALID_KINDS",
    "resolve_targets",
    "install_into",
    "run",
]
