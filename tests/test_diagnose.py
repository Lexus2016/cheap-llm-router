"""Tests for ``cheap diagnose`` (commands/diagnose.py).

Each test builds a synthetic ``home`` directory with the v9.0 surface
(or a partial subset) and asserts the right Check statuses and exit code.

The non-negotiable test is ``test_diagnose_does_not_print_api_key`` —
the literal API key must NEVER appear in any output mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cheap_llm.commands import diagnose as diag


_FAKE_KEY = "sk-test-DO-NOT-LEAK-this-must-stay-redacted"

_V9_CLAUDE_MD = (
    "# Claude Code Global Instructions\n"
    "> Version: 9.0 | Updated: 2026-05-07\n"
    "\n"
    "## ABSOLUTE PRE-FLIGHT (run before EVERY response)\n"
    "preflight body\n"
)

_V8_CLAUDE_MD = (
    "# Claude Code Global Instructions\n"
    "> Version: 8.0 | Updated: 2026-05-01\n"
    "\n"
    "## Some Section\n"
    "no preflight here\n"
)

_RULES_JSON = '{"version": "9.0", "key1": 1, "key2": 2}\n'
_ACTIVATION_MD = "[STATE] lang=uk | cheap=on | automem=off | ssot_triggered=no | self_check=passed\n"

_SETTINGS_WITH_BLOCK_HOOK = json.dumps(
    {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Read",
                    "hooks": [
                        {"type": "command", "command": "cheap pretooluse-hook"}
                    ],
                }
            ]
        }
    }
)
_SETTINGS_WITH_SOFT_HOOK = json.dumps(
    {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "cheap pretooluse-hook --soft",
                        }
                    ],
                }
            ]
        }
    }
)
_SETTINGS_NO_HOOK = json.dumps({"hooks": {"PreToolUse": []}})


def _build_v9_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True)
    (claude / "CLAUDE.md").write_text(_V9_CLAUDE_MD, encoding="utf-8")
    (claude / "RULES.json").write_text(_RULES_JSON, encoding="utf-8")
    (claude / "ACTIVATION.md").write_text(_ACTIVATION_MD, encoding="utf-8")
    (claude / "settings.json").write_text(_SETTINGS_WITH_BLOCK_HOOK, encoding="utf-8")
    return home


@pytest.fixture
def fake_config(tmp_path: Path, monkeypatch) -> Path:
    """Point cheap_llm.config at a tmp config with a literal fake key."""
    cfg_dir = tmp_path / "xdg-config" / "cheap-llm"
    cfg_dir.mkdir(parents=True)
    cfg_path = cfg_dir / "config.yaml"
    cfg_path.write_text(
        "provider:\n"
        "  base_url: https://example.invalid/v1\n"
        "  api_key: " + _FAKE_KEY + "\n"
        "  api_key_env: null\n"
        "  model: test/model\n"
        "  temperature: 0.0\n"
        "  request_timeout_seconds: 30\n"
        "read:\n"
        "  max_summary_tokens: 600\n"
        "  max_input_chars: 60000\n"
        "  prompt_template: 'Q: {question}\\nA:'\n"
        "secrets_patterns: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    return cfg_path


def test_diagnose_all_present_passes(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = _build_v9_home(tmp_path)
    rc = diag.run(home=home)
    out = capsys.readouterr().out
    assert rc == diag.EXIT_OK
    assert "all checks passed" in out
    assert "v9.0 native" in out


def test_diagnose_claude_md_missing_fails(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    # No CLAUDE.md, RULES.json, ACTIVATION.md, settings.json.
    rc = diag.run(home=home)
    assert rc == diag.EXIT_GENERIC_ERROR
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "claude.md" in out


def test_diagnose_v8_claude_md_warns(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = _build_v9_home(tmp_path)
    (home / ".claude" / "CLAUDE.md").write_text(_V8_CLAUDE_MD, encoding="utf-8")
    rc = diag.run(home=home)
    out = capsys.readouterr().out
    # v8.0 is not a FAIL — still functional. Just WARN.
    assert rc == diag.EXIT_OK
    assert "WARN" in out
    assert "claude.md" in out


def test_diagnose_settings_missing_fails_hook_check(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = _build_v9_home(tmp_path)
    (home / ".claude" / "settings.json").unlink()
    rc = diag.run(home=home)
    out = capsys.readouterr().out
    assert rc == diag.EXIT_GENERIC_ERROR
    assert "hook.pretooluse.read" in out
    assert "FAIL" in out


def test_diagnose_hook_soft_mode_warns(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = _build_v9_home(tmp_path)
    (home / ".claude" / "settings.json").write_text(
        _SETTINGS_WITH_SOFT_HOOK, encoding="utf-8"
    )
    rc = diag.run(home=home)
    out = capsys.readouterr().out
    assert rc == diag.EXIT_OK  # WARN doesn't fail the run
    assert "soft mode" in out


def test_diagnose_json_output_is_valid_json(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    home = _build_v9_home(tmp_path)
    rc = diag.run(home=home, json_output=True)
    out = capsys.readouterr().out
    assert rc == diag.EXIT_OK
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert all(set(item.keys()) >= {"name", "status", "detail"} for item in parsed)
    names = [item["name"] for item in parsed]
    assert "claude.md" in names
    assert "api key" in names


def test_diagnose_does_not_print_api_key(
    tmp_path: Path, fake_config: Path, capsys
) -> None:
    """SECURITY: the literal API key must never appear in diagnose output.

    Both default and JSON mode are exercised. If this test ever fails,
    diagnose has leaked a credential — fix immediately, do not relax
    the assertion.
    """
    home = _build_v9_home(tmp_path)

    diag.run(home=home)
    text_out = capsys.readouterr().out
    assert _FAKE_KEY not in text_out

    diag.run(home=home, json_output=True)
    json_out = capsys.readouterr().out
    assert _FAKE_KEY not in json_out
