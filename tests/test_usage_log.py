"""Tests for the append-only usage log."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cheap_llm import usage_log


def _read_lines(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]


# --- log_path resolution -----------------------------------------------------

def test_log_path_uses_default_under_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = usage_log.log_path()
    assert p == tmp_path / ".cache" / "cheap-llm" / "usage.log"


def test_log_path_honours_xdg_cache_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    p = usage_log.log_path()
    assert p == tmp_path / "xdg" / "cheap-llm" / "usage.log"


# --- record() — happy path ---------------------------------------------------

def test_record_creates_file_and_writes_one_jsonl_line(tmp_path: Path) -> None:
    log = tmp_path / "usage.log"
    usage_log.record(
        cmd="read",
        model="deepseek/test",
        input_chars=100,
        output_tokens=42,
        elapsed_ms=120,
        path=log,
        files=3,
    )
    entries = _read_lines(log)
    assert len(entries) == 1
    e = entries[0]
    # Required schema fields.
    assert e["cmd"] == "read"
    assert e["model"] == "deepseek/test"
    assert e["input_chars"] == 100
    assert e["output_tokens"] == 42
    assert e["elapsed_ms"] == 120
    assert e["files"] == 3
    # Timestamp is ISO-8601 UTC with trailing Z.
    assert e["ts"].endswith("Z")
    assert "T" in e["ts"]


def test_record_appends_preserving_existing_entries(tmp_path: Path) -> None:
    log = tmp_path / "usage.log"
    usage_log.record(
        cmd="read", model="m", input_chars=1, output_tokens=1,
        elapsed_ms=1, path=log, files=1,
    )
    usage_log.record(
        cmd="extract", model="m", input_chars=2, output_tokens=2,
        elapsed_ms=2, path=log, n_messages=5, backend="claude",
    )
    entries = _read_lines(log)
    assert len(entries) == 2
    assert entries[0]["cmd"] == "read"
    assert entries[1]["cmd"] == "extract"
    assert entries[1]["n_messages"] == 5
    assert entries[1]["backend"] == "claude"


def test_record_drops_none_extras(tmp_path: Path) -> None:
    """Optional fields with value None should not bloat the JSON line."""
    log = tmp_path / "usage.log"
    usage_log.record(
        cmd="read", model="m", input_chars=1, output_tokens=1,
        elapsed_ms=1, path=log,
        files=None, n_messages=None, backend=None,
    )
    e = _read_lines(log)[0]
    assert "files" not in e
    assert "n_messages" not in e
    assert "backend" not in e


def test_record_creates_parent_dirs(tmp_path: Path) -> None:
    log = tmp_path / "deeply" / "nested" / "usage.log"
    usage_log.record(
        cmd="read", model="m", input_chars=1, output_tokens=1,
        elapsed_ms=1, path=log, files=1,
    )
    assert log.exists()


# --- record() — best-effort failure modes ------------------------------------

def test_record_swallows_io_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    """If the log can't be written, the user's read/extract MUST still
    succeed. We just emit one stderr warning and move on."""
    log = tmp_path / "usage.log"

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", boom)
    # Must not raise.
    usage_log.record(
        cmd="read", model="m", input_chars=1, output_tokens=1,
        elapsed_ms=1, path=log, files=1,
    )
    err = capsys.readouterr().err
    assert "could not append to usage log" in err
    assert "disk full" in err


def test_record_swallows_when_parent_unwritable(tmp_path: Path, capsys) -> None:
    # Create a read-only parent dir; mkdir(exist_ok=True) of a sibling
    # subdir under it will fail on most filesystems.
    if os.geteuid() == 0:
        pytest.skip("running as root, perm bits ignored")
    parent = tmp_path / "ro"
    parent.mkdir()
    parent.chmod(0o500)
    try:
        log = parent / "child" / "usage.log"
        usage_log.record(
            cmd="read", model="m", input_chars=1, output_tokens=1,
            elapsed_ms=1, path=log, files=1,
        )
        err = capsys.readouterr().err
        assert "could not append" in err
    finally:
        parent.chmod(0o700)


# --- read.py / extract.py integration ----------------------------------------

def test_read_records_to_usage_log(tmp_path: Path, monkeypatch) -> None:
    """`cheap read` calls usage_log.record() with files= populated."""
    from cheap_llm.commands import read as read_cmd

    f = tmp_path / "x.py"
    f.write_text("def x(): pass\n", encoding="utf-8")
    log = tmp_path / "usage.log"
    monkeypatch.setattr(usage_log, "log_path", lambda: log)

    class Fake:
        text = "summary"
        output_tokens = 7
        elapsed_ms = 11

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        "cheap_llm.commands.read.call_provider",
        lambda cfg, prompt: Fake(),
    )

    rc = read_cmd.run(files=[str(f)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_OK

    entries = _read_lines(log)
    assert len(entries) == 1
    e = entries[0]
    assert e["cmd"] == "read"
    assert e["files"] == 1
    assert e["output_tokens"] == 7
    assert "n_messages" not in e
    assert "backend" not in e


def test_extract_records_to_usage_log(tmp_path: Path, monkeypatch) -> None:
    """`cheap extract` calls usage_log.record() with n_messages + backend."""
    from cheap_llm.commands import extract as extract_cmd

    fixture = (
        Path(__file__).parent / "fixtures" / "sample_session_claude.jsonl"
    )
    log = tmp_path / "usage.log"
    monkeypatch.setattr(usage_log, "log_path", lambda: log)

    class Fake:
        text = "digest"
        output_tokens = 9
        elapsed_ms = 13

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(
        "cheap_llm.commands.extract.call_provider",
        lambda cfg, prompt: Fake(),
    )

    rc = extract_cmd.run(
        jsonl=str(fixture),
        session_id=None,
        question=None,
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_OK

    entries = _read_lines(log)
    assert len(entries) == 1
    e = entries[0]
    assert e["cmd"] == "extract"
    assert e["backend"] == "explicit"
    assert e["n_messages"] >= 1
    assert "files" not in e
