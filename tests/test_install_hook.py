"""Tests for `cheap install-hook`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cheap_llm.commands import install_hook as cmd


def _settings(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "settings.json"


def _read(tmp_path: Path) -> dict:
    return json.loads(_settings(tmp_path).read_text(encoding="utf-8"))


def test_install_creates_settings_when_missing(tmp_path: Path) -> None:
    rc = cmd.run(force=False, home=tmp_path)
    assert rc == cmd.EXIT_OK
    data = _read(tmp_path)
    pre = data["hooks"]["PreToolUse"]
    assert len(pre) == 1
    assert pre[0]["matcher"] == "Read"
    assert pre[0]["hooks"][0]["command"] == "cheap pretooluse-hook"


def test_install_preserves_existing_unrelated_hooks(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.parent.mkdir(parents=True)
    existing = {
        "env": {"FOO": "1"},
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "rtk-rewrite.sh"}
                ]},
            ],
            "PostToolUse": [
                {"matcher": "Edit", "hooks": [
                    {"type": "command", "command": "lint.sh"}
                ]},
            ],
        },
    }
    settings.write_text(json.dumps(existing), encoding="utf-8")

    cmd.run(force=False, home=tmp_path)

    data = _read(tmp_path)
    # Untouched.
    assert data["env"] == {"FOO": "1"}
    assert any(
        e["matcher"] == "Bash" for e in data["hooks"]["PreToolUse"]
    )
    assert data["hooks"]["PostToolUse"][0]["matcher"] == "Edit"
    # Added.
    read_entries = [
        e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Read"
    ]
    assert len(read_entries) == 1


def test_install_is_idempotent_without_force(tmp_path: Path, capsys) -> None:
    cmd.run(force=False, home=tmp_path)
    capsys.readouterr()
    # Snapshot.
    before = _settings(tmp_path).read_text(encoding="utf-8")
    rc = cmd.run(force=False, home=tmp_path)
    after = _settings(tmp_path).read_text(encoding="utf-8")
    assert rc == cmd.EXIT_OK
    assert before == after
    err = capsys.readouterr().err
    assert "already installed" in err


def test_force_replaces_existing_entry(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.parent.mkdir(parents=True)
    stale = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Read", "hooks": [
                    # Note: matches our recogniser ('pretooluse-hook' substr).
                    {"type": "command",
                     "command": "/old/path/pretooluse-hook --legacy"}
                ]},
            ],
        },
    }
    settings.write_text(json.dumps(stale), encoding="utf-8")

    rc = cmd.run(force=True, home=tmp_path)
    assert rc == cmd.EXIT_OK
    data = _read(tmp_path)
    pre = data["hooks"]["PreToolUse"]
    # Single entry, fresh command.
    assert len(pre) == 1
    assert pre[0]["hooks"][0]["command"] == "cheap pretooluse-hook"


def test_malformed_settings_returns_error(tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text("{not json", encoding="utf-8")
    rc = cmd.run(force=False, home=tmp_path)
    assert rc == cmd.EXIT_GENERIC_ERROR
    err = capsys.readouterr().err
    assert "not valid JSON" in err


def test_does_not_duplicate_when_other_read_matchers_exist(
    tmp_path: Path,
) -> None:
    """If there's a Read matcher pointing at someone else's hook, we add
    OUR entry alongside (no merge), so we don't accidentally take over."""
    settings = _settings(tmp_path)
    settings.parent.mkdir(parents=True)
    existing = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Read", "hooks": [
                    {"type": "command", "command": "/some/other/tool.sh"}
                ]},
            ],
        },
    }
    settings.write_text(json.dumps(existing), encoding="utf-8")

    cmd.run(force=False, home=tmp_path)
    data = _read(tmp_path)
    pre = data["hooks"]["PreToolUse"]
    # Two entries with matcher=Read: theirs and ours.
    assert len([e for e in pre if e["matcher"] == "Read"]) == 2


# --- soft mode --------------------------------------------------------------

def test_install_default_writes_block_command(tmp_path: Path) -> None:
    """Without --soft, command is the bare 'cheap pretooluse-hook' (block)."""
    cmd.run(force=False, soft=False, home=tmp_path)
    data = _read(tmp_path)
    cmd_str = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd_str == "cheap pretooluse-hook"
    assert "--soft" not in cmd_str


def test_install_soft_writes_soft_command(tmp_path: Path) -> None:
    """With --soft, command carries the --soft flag."""
    cmd.run(force=False, soft=True, home=tmp_path)
    data = _read(tmp_path)
    cmd_str = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd_str == "cheap pretooluse-hook --soft"


def test_install_force_can_switch_block_to_soft(tmp_path: Path) -> None:
    """User initially installs block, then runs `--force --soft` to switch."""
    cmd.run(force=False, soft=False, home=tmp_path)  # block
    cmd.run(force=True, soft=True, home=tmp_path)    # → soft
    data = _read(tmp_path)
    pre = [e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Read"]
    assert len(pre) == 1
    assert pre[0]["hooks"][0]["command"] == "cheap pretooluse-hook --soft"


def test_install_force_can_switch_soft_to_block(tmp_path: Path) -> None:
    """User initially installs --soft, then runs `--force` to switch back."""
    cmd.run(force=False, soft=True, home=tmp_path)   # soft
    cmd.run(force=True, soft=False, home=tmp_path)   # → block
    data = _read(tmp_path)
    pre = [e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Read"]
    assert len(pre) == 1
    assert pre[0]["hooks"][0]["command"] == "cheap pretooluse-hook"


def test_install_idempotent_recognizes_either_mode(tmp_path: Path) -> None:
    """Without --force, we skip regardless of which mode is installed.
    The user must opt in via --force to switch modes."""
    cmd.run(force=False, soft=False, home=tmp_path)  # block installed
    rc = cmd.run(force=False, soft=True, home=tmp_path)
    assert rc == cmd.EXIT_OK
    data = _read(tmp_path)
    cmd_str = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    # Stayed at block — no force, no switch.
    assert cmd_str == "cheap pretooluse-hook"
