"""``cheap diagnose`` — health check for the v9.0 alignment surface.

Reports on every file the rule + hook integration depends on and on the
package's own configuration. Exit 1 on any FAIL; WARN and INFO are still
considered success.

Layout (in display order):
    version            INFO  cheap-llm-router X.Y.Z (rule template v=N)
    claude.md          PASS  v9.0 native (PRE-FLIGHT detected) | WARN | FAIL
    rules.json         PASS  valid JSON                         | WARN
    activation.md      PASS  [STATE] token spec found           | WARN
    settings.json      PASS  valid JSON                         | WARN
    hook.pretooluse.read  PASS block | WARN soft | FAIL not installed
    cheap config       PASS  model=X (path)                     | WARN | FAIL
    api key            PASS  resolved (value redacted)          | FAIL

The "value redacted" wording is load-bearing — we MUST never print the
literal API key, including under any future `--verbose` flag. The
matching test is non-negotiable.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import typer

from .. import RULE_TEMPLATE_VERSION, __version__
from .. import config as config_mod

EXIT_OK = 0
EXIT_GENERIC_ERROR = 1

Status = Literal["PASS", "WARN", "FAIL", "INFO"]

_STATUS_GLYPH: dict[str, str] = {
    "PASS": "✓",
    "WARN": "!",
    "FAIL": "✗",
    "INFO": "·",
}

_V9_PREFLIGHT_MARKER = "## ABSOLUTE PRE-FLIGHT"
_V9_VERSION_RE = re.compile(r"^>\s*Version:\s*(\d+(?:\.\d+)?)", re.MULTILINE)
_ACTIVATION_TOKEN_RE = re.compile(r"\[STATE\]\s*lang=", re.IGNORECASE)
_HOOK_COMMAND_TOKEN = "cheap pretooluse-hook"


@dataclass
class Check:
    name: str
    status: Status
    detail: str


def _check_versions() -> list[Check]:
    return [
        Check(
            "version",
            "INFO",
            f"cheap-llm-router {__version__} "
            f"(rule template v={RULE_TEMPLATE_VERSION})",
        )
    ]


def _check_claude_md(home: Path) -> list[Check]:
    p = home / ".claude" / "CLAUDE.md"
    if not p.exists():
        return [Check("claude.md", "FAIL", f"missing: {p}")]
    text = p.read_text(encoding="utf-8", errors="replace")
    has_preflight = _V9_PREFLIGHT_MARKER in text
    m = _V9_VERSION_RE.search(text)
    version_str = m.group(1) if m else "unknown"
    if has_preflight and version_str.startswith("9"):
        return [Check("claude.md", "PASS", f"v{version_str} native (PRE-FLIGHT detected, {p})")]
    if has_preflight:
        return [Check("claude.md", "PASS", f"PRE-FLIGHT detected, version: {version_str} ({p})")]
    if version_str != "unknown":
        return [Check("claude.md", "WARN", f"v{version_str} — pre-v9 layout, no PRE-FLIGHT ({p})")]
    return [Check("claude.md", "WARN", f"present but no v9 PRE-FLIGHT marker ({p})")]


def _check_rules_json(home: Path) -> list[Check]:
    p = home / ".claude" / "RULES.json"
    if not p.exists():
        return [Check("rules.json", "WARN", f"missing: {p}")]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [Check("rules.json", "WARN", f"invalid JSON: {e}")]
    n_keys = len(data) if isinstance(data, dict) else "non-dict"
    return [Check("rules.json", "PASS", f"valid JSON ({n_keys} top-level keys, {p})")]


def _check_activation_md(home: Path) -> list[Check]:
    p = home / ".claude" / "ACTIVATION.md"
    if not p.exists():
        return [Check("activation.md", "WARN", f"missing: {p}")]
    text = p.read_text(encoding="utf-8", errors="replace")
    if _ACTIVATION_TOKEN_RE.search(text):
        return [Check("activation.md", "PASS", f"[STATE] token spec found ({p})")]
    return [Check("activation.md", "WARN", f"present but no [STATE] token spec ({p})")]


def _check_settings_and_hook(home: Path) -> list[Check]:
    p = home / ".claude" / "settings.json"
    if not p.exists():
        return [
            Check("settings.json", "WARN", f"missing: {p}"),
            Check("hook.pretooluse.read", "FAIL", "no settings.json — hook not installable"),
        ]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [
            Check("settings.json", "WARN", f"invalid JSON: {e}"),
            Check("hook.pretooluse.read", "FAIL", "cannot inspect — settings.json invalid"),
        ]

    found_mode: str | None = None
    if isinstance(data, dict):
        for entry in data.get("hooks", {}).get("PreToolUse", []) or []:
            if not isinstance(entry, dict) or entry.get("matcher") != "Read":
                continue
            for h in entry.get("hooks", []) or []:
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                if _HOOK_COMMAND_TOKEN in cmd:
                    found_mode = "soft" if "--soft" in cmd else "block"
                    break
            if found_mode:
                break

    settings_ok = Check("settings.json", "PASS", f"valid JSON ({p})")
    if found_mode == "block":
        return [settings_ok, Check("hook.pretooluse.read", "PASS", "installed (block mode)")]
    if found_mode == "soft":
        return [settings_ok, Check("hook.pretooluse.read", "WARN", "installed (soft mode)")]
    return [
        settings_ok,
        Check("hook.pretooluse.read", "FAIL", "not installed — run `cheap install-hook`"),
    ]


def _check_config_and_key() -> list[Check]:
    cfg_path = config_mod.config_path()
    if not cfg_path.exists():
        return [
            Check("cheap config", "WARN", f"missing: {cfg_path} (run `cheap config path` to create)"),
            Check("api key", "INFO", "skipped — no config"),
        ]
    try:
        cfg = config_mod.load_config()
    except Exception as e:  # surfacing any load error as FAIL is intentional
        return [
            Check("cheap config", "FAIL", f"load failed: {type(e).__name__}: {e}"),
            Check("api key", "INFO", "skipped — config invalid"),
        ]
    cfg_ok = Check(
        "cheap config",
        "PASS",
        f"model={cfg.provider.model} ({cfg_path})",
    )
    if config_mod.resolve_api_key(cfg):
        return [cfg_ok, Check("api key", "PASS", "resolved (value redacted)")]
    if cfg.provider.api_key_env:
        return [
            cfg_ok,
            Check("api key", "FAIL", f"env {cfg.provider.api_key_env!r} not set (or empty)"),
        ]
    return [cfg_ok, Check("api key", "FAIL", "no api_key or api_key_env configured")]


def _render_table(checks: list[Check]) -> None:
    name_w = max(len(c.name) for c in checks)
    for c in checks:
        glyph = _STATUS_GLYPH.get(c.status, "?")
        typer.echo(f"{glyph} {c.status:<4} {c.name:<{name_w}}  {c.detail}")
    n_fail = sum(1 for c in checks if c.status == "FAIL")
    n_warn = sum(1 for c in checks if c.status == "WARN")
    typer.echo("")
    if n_fail:
        typer.echo(f"Result: {n_fail} FAIL, {n_warn} WARN")
    elif n_warn:
        typer.echo(f"Result: {n_warn} WARN (still functional)")
    else:
        typer.echo("Result: all checks passed")


def run(
    *,
    json_output: bool = False,
    home: Path | None = None,
) -> int:
    home = home or Path.home()
    checks: list[Check] = []
    checks += _check_versions()
    checks += _check_claude_md(home)
    checks += _check_rules_json(home)
    checks += _check_activation_md(home)
    checks += _check_settings_and_hook(home)
    checks += _check_config_and_key()

    if json_output:
        typer.echo(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        _render_table(checks)

    return EXIT_GENERIC_ERROR if any(c.status == "FAIL" for c in checks) else EXIT_OK


__all__ = ["EXIT_OK", "EXIT_GENERIC_ERROR", "Check", "run"]
