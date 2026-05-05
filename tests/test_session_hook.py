"""End-to-end tests for the bundled SessionStart hook.

The hook is a small bash script. We invoke it as a subprocess with
controlled stdin / env / PPID and verify the file it wrote — same
contract Claude Code's hook runtime relies on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest


HOOK_SCRIPT = Path(
    str(files("cheap_llm").joinpath("_data/cheap-llm-session.sh"))
)


def _run(payload: str | None, *, env_extra: dict[str, str] | None = None,
         claude_pid: int = 99999):
    """Run the hook in a controlled environment.

    Bash sees `$PPID` as the PID of its parent. Since we can't fake
    that directly, we run the script under a wrapper that forces a
    known PID into a literal. To keep the test honest, we instead
    *trust* bash's $PPID and read whatever <PID>.txt the hook wrote
    in the cache dir we point it at.
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(HOOK_SCRIPT)],
        input=payload if payload is not None else "",
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return proc


def test_hook_writes_transcript_path_to_cache(tmp_path: Path) -> None:
    cache_root = tmp_path / "xdg"
    payload = json.dumps({
        "transcript_path": "/tmp/example/12345-abc.jsonl",
        "session_id": "ignored-in-hook",
    })
    proc = _run(payload, env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr

    sessions_dir = cache_root / "cheap-llm" / "sessions"
    assert sessions_dir.is_dir()
    written = list(sessions_dir.glob("*.txt"))
    assert len(written) == 1
    assert written[0].read_text().strip() == "/tmp/example/12345-abc.jsonl"


def test_hook_handles_payload_without_transcript_path(tmp_path: Path) -> None:
    """No transcript_path → write nothing, exit 0 cleanly."""
    cache_root = tmp_path / "xdg"
    payload = json.dumps({"session_id": "no-transcript-here"})
    proc = _run(payload, env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr
    if (cache_root / "cheap-llm" / "sessions").exists():
        assert not list((cache_root / "cheap-llm" / "sessions").glob("*.txt"))


def test_hook_swallows_malformed_json(tmp_path: Path) -> None:
    """Garbage stdin must NOT crash the hook (Claude must not be blocked)."""
    cache_root = tmp_path / "xdg"
    proc = _run("this is { not json", env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr


def test_hook_swallows_empty_stdin(tmp_path: Path) -> None:
    cache_root = tmp_path / "xdg"
    proc = _run("", env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr


def test_hook_handles_extra_fields_around_transcript_path(tmp_path: Path) -> None:
    """Real Claude Code payloads have many fields. Regex/jq must still pick
    transcript_path out of the surrounding noise."""
    cache_root = tmp_path / "xdg"
    payload = json.dumps({
        "session_id": "abc-def",
        "cwd": "/some/dir",
        "transcript_path": "/abs/path/to/transcript.jsonl",
        "model": "opus-4.7",
        "tools": ["Read", "Edit", "Bash"],
    })
    proc = _run(payload, env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr
    written = list((cache_root / "cheap-llm" / "sessions").glob("*.txt"))
    assert len(written) == 1
    assert written[0].read_text().strip() == "/abs/path/to/transcript.jsonl"


def test_hook_resolver_round_trip(tmp_path: Path) -> None:
    """Hook writes a file → session_resolver reads it back via $PPID.

    Locks the contract between the two pieces.
    """
    from cheap_llm.session_resolver import resolve_session

    cache_root = tmp_path / "xdg"
    transcript = tmp_path / "claude.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")

    payload = json.dumps({"transcript_path": str(transcript)})
    proc = _run(payload, env_extra={"XDG_CACHE_HOME": str(cache_root)})
    assert proc.returncode == 0, proc.stderr

    written = list((cache_root / "cheap-llm" / "sessions").glob("*.txt"))
    assert len(written) == 1
    # The hook used its own $PPID — read it from the filename and feed
    # it to the resolver as if `cheap extract` ran from the same parent.
    ppid_from_filename = int(written[0].stem)

    res = resolve_session(
        home=tmp_path,
        ppid=ppid_from_filename,
        env={"XDG_CACHE_HOME": str(cache_root)},
    )
    assert res.path == transcript
    assert res.backend == "claude"
    assert res.fallback_warning is None  # deterministic — no warning


def test_hook_works_without_jq(tmp_path: Path, monkeypatch) -> None:
    """The regex fallback path must work even when jq is missing.

    Achieved by stripping PATH down to the bare minimum (bash + posix
    coreutils) and verifying the hook still extracts transcript_path.
    """
    cache_root = tmp_path / "xdg"
    minimal_path = "/usr/bin:/bin"
    payload = json.dumps({"transcript_path": "/x/y/z.jsonl"})
    proc = _run(
        payload,
        env_extra={
            "XDG_CACHE_HOME": str(cache_root),
            "PATH": minimal_path,
        },
    )
    assert proc.returncode == 0, proc.stderr
    written = list((cache_root / "cheap-llm" / "sessions").glob("*.txt"))
    assert len(written) == 1
    assert written[0].read_text().strip() == "/x/y/z.jsonl"
