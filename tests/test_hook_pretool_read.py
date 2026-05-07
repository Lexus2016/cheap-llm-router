"""Unit tests for the PreToolUse:Read hook decision logic."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from cheap_llm import hook_pretool_read as hook


def _payload(file_path: str, *, offset=None, limit=None,
             transcript_path: str = "", session_id: str = "test") -> dict:
    return {
        "tool_name": "Read",
        "tool_input": {"file_path": file_path,
                       **({"offset": offset} if offset is not None else {}),
                       **({"limit": limit} if limit is not None else {})},
        "session_id": session_id,
        "transcript_path": transcript_path,
    }


def _write(tmp_path: Path, name: str, lines: int) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(f"line {i}" for i in range(lines)) + "\n",
                 encoding="utf-8")
    return p


# --- skip rules -------------------------------------------------------------

def test_skip_for_image_extension(tmp_path: Path) -> None:
    f = _write(tmp_path, "x.png", 1000)
    skip, u, a = hook.decide(_payload(str(f)))
    assert skip == "binary-or-image"
    assert (u, a) == ("", "")


def test_skip_for_secrets_pattern(tmp_path: Path) -> None:
    f = _write(tmp_path, ".env.local", 500)
    skip, _, _ = hook.decide(_payload(str(f)))
    assert skip == "secrets-pattern"


def test_skip_for_auth_in_path(tmp_path: Path) -> None:
    nested = tmp_path / "src" / "auth"
    nested.mkdir(parents=True)
    f = nested / "service.py"
    f.write_text("\n".join("x" * 80 for _ in range(500)), encoding="utf-8")
    skip, _, _ = hook.decide(_payload(str(f)))
    assert skip == "secrets-pattern"


def test_skip_when_offset_set(tmp_path: Path) -> None:
    f = _write(tmp_path, "big.py", 1000)
    skip, _, _ = hook.decide(_payload(str(f), offset=50))
    assert skip == "line-targeted"


def test_skip_when_limit_set(tmp_path: Path) -> None:
    f = _write(tmp_path, "big.py", 1000)
    skip, _, _ = hook.decide(_payload(str(f), limit=20))
    assert skip == "line-targeted"


def test_skip_short_file(tmp_path: Path) -> None:
    f = _write(tmp_path, "small.py", 50)  # < SHORT_FILE_LINES (100)
    skip, _, _ = hook.decide(_payload(str(f)))
    assert skip == "short-file"


def test_skip_unreadable_file(tmp_path: Path) -> None:
    skip, _, _ = hook.decide(_payload(str(tmp_path / "nope.py")))
    assert skip == "file-unreadable"


def test_skip_binary_content(tmp_path: Path) -> None:
    f = tmp_path / "raw.bin"
    f.write_bytes(b"\x00\x01\x00\x02\x00\x03" * 200)  # NUL-heavy
    skip, _, _ = hook.decide(_payload(str(f)))
    assert skip == "binary-content"


# --- recent-edit-on-same-file -----------------------------------------------

def _write_jsonl(path: Path, tool_uses: list[tuple[str, str]]) -> None:
    """Write a fake assistant transcript with the given tool_uses sequence."""
    lines = []
    for i, (name, file_path) in enumerate(tool_uses):
        lines.append(json.dumps({
            "type": "assistant",
            "timestamp": f"2026-05-07T12:00:{i:02d}.000Z",
            "message": {"content": [{
                "type": "tool_use",
                "name": name,
                "input": {"file_path": file_path},
            }]},
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_skip_when_recent_edit_on_same_file(tmp_path: Path) -> None:
    f = _write(tmp_path, "code.py", 500)
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        ("Read", str(f)),
        ("Edit", str(f)),  # legitimate Read-then-Edit
    ])
    skip, _, _ = hook.decide(
        _payload(str(f), transcript_path=str(transcript))
    )
    assert skip == "recent-edit-same-file"


def test_no_skip_when_recent_edit_on_different_file(tmp_path: Path) -> None:
    f = _write(tmp_path, "code.py", 500)
    other = _write(tmp_path, "other.py", 500)
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [("Edit", str(other))])
    skip, u, _ = hook.decide(
        _payload(str(f), transcript_path=str(transcript))
    )
    # Above thresholds → nudge fires; we check skip is empty (no skip).
    assert skip == ""
    assert u  # nudge text present


# --- nudge triggers ---------------------------------------------------------

def test_nudge_for_large_file_no_recent_reads(tmp_path: Path) -> None:
    f = _write(tmp_path, "big.py", 500)  # > LARGE_FILE_LINES
    skip, user_msg, agent_msg = hook.decide(_payload(str(f)))
    assert skip == ""
    assert "Large file" in user_msg
    assert "500 lines" in user_msg
    assert "DELEGATION HINT" in agent_msg
    assert "cheap read" in agent_msg


def test_strong_nudge_for_multi_read_pattern(tmp_path: Path) -> None:
    f1 = _write(tmp_path, "a.py", 500)
    f2 = _write(tmp_path, "b.py", 500)
    f3 = _write(tmp_path, "c.py", 500)
    transcript = tmp_path / "session.jsonl"
    _write_jsonl(transcript, [
        ("Read", str(f1)),
        ("Read", str(f2)),
    ])
    skip, user_msg, agent_msg = hook.decide(
        _payload(str(f3), transcript_path=str(transcript))
    )
    assert skip == ""
    assert "Multi-file pattern" in user_msg
    assert "3 full reads" in user_msg  # 2 prior + this one
    assert "STOP and run" in agent_msg


def test_no_nudge_for_borderline_size(tmp_path: Path) -> None:
    """File ≥ SHORT but < LARGE and no multi-read pattern → silent."""
    f = _write(tmp_path, "med.py", 150)  # 100 ≤ 150 < 200
    skip, user_msg, agent_msg = hook.decide(_payload(str(f)))
    assert skip == "below-thresholds"
    assert (user_msg, agent_msg) == ("", "")


# --- main() entry point -----------------------------------------------------

def test_main_emits_allow_with_reason_on_nudge(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    f = _write(tmp_path, "big.py", 500)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(str(f)))))
    # Send hook log to a tmp dir to avoid polluting ~/.cache.
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    rc = hook.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "Large file" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert out["hookSpecificOutput"]["additionalContext"]


def test_main_emits_bare_allow_on_skip(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    f = _write(tmp_path, "small.py", 50)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(str(f)))))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    rc = hook.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    out_h = out["hookSpecificOutput"]
    assert out_h["permissionDecision"] == "allow"
    assert "permissionDecisionReason" not in out_h
    assert "additionalContext" not in out_h


def test_main_robust_to_malformed_stdin(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    rc = hook.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_logs_decisions_to_hook_log(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    f = _write(tmp_path, "big.py", 500)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(str(f)))))
    cache = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    hook.main()
    log = cache / "cheap-llm" / "hook.log"
    assert log.exists()
    rec = json.loads(log.read_text().strip())
    assert rec["nudged"] is True
    assert rec["file"] == str(f)
