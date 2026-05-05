"""Tests for cheap_llm.session_resolver and cheap_llm.commands.extract.

Provider is mocked throughout; no network in this file. Real-call
integration coverage is via test_read_integration.py — extract reuses
the same call_provider path, so a separate paid test is redundant.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cheap_llm import session_resolver
from cheap_llm.commands import extract as extract_cmd
from cheap_llm.session_resolver import (
    AmbiguousSession,
    NoSessionFound,
    resolve_session,
)


FIX = Path(__file__).parent / "fixtures"
CLAUDE_FX = FIX / "sample_session_claude.jsonl"
CODEX_FX = FIX / "sample_session_codex.jsonl"


# --- session_resolver: explicit paths and ids -------------------------------

def test_resolver_uses_explicit_jsonl(tmp_path: Path) -> None:
    res = resolve_session(jsonl=str(CLAUDE_FX), home=tmp_path, env={})
    assert res.path == CLAUDE_FX
    assert res.backend == "explicit"


def test_resolver_jsonl_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(NoSessionFound):
        resolve_session(jsonl=str(tmp_path / "nope.jsonl"),
                        home=tmp_path, env={})


def test_resolver_session_id_finds_claude_jsonl(tmp_path: Path) -> None:
    sid = "11111111-1111-4111-8111-111111111111"
    slug_dir = tmp_path / ".claude" / "projects" / "-tmp-x"
    slug_dir.mkdir(parents=True)
    target = slug_dir / f"{sid}.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    res = resolve_session(session_id=sid, home=tmp_path, env={})
    assert res.path == target
    assert res.backend == "claude"


def test_resolver_session_id_finds_codex_rollout(tmp_path: Path) -> None:
    tid = "22222222-2222-4222-8222-222222222222"
    day = tmp_path / ".codex" / "sessions" / "2026" / "05" / "05"
    day.mkdir(parents=True)
    target = day / f"rollout-2026-05-05T12-00-00-{tid}.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    res = resolve_session(session_id=tid, home=tmp_path, env={})
    assert res.path == target
    assert res.backend == "codex"


def test_resolver_session_id_no_match_raises(tmp_path: Path) -> None:
    with pytest.raises(NoSessionFound):
        resolve_session(session_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
                        home=tmp_path, env={})


def test_resolver_session_id_ambiguous_raises(tmp_path: Path) -> None:
    """Same id under both backends → user must disambiguate."""
    sid = "33333333-3333-4333-8333-333333333333"
    slug_dir = tmp_path / ".claude" / "projects" / "-tmp-x"
    slug_dir.mkdir(parents=True)
    (slug_dir / f"{sid}.jsonl").write_text("{}\n", encoding="utf-8")
    day = tmp_path / ".codex" / "sessions" / "2026" / "05" / "05"
    day.mkdir(parents=True)
    (day / f"rollout-x-{sid}.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(AmbiguousSession):
        resolve_session(session_id=sid, home=tmp_path, env={})


# --- session_resolver: env / hook / fallback --------------------------------

def test_resolver_codex_thread_id_takes_priority(tmp_path: Path) -> None:
    tid = "44444444-4444-4444-8444-444444444444"
    day = tmp_path / ".codex" / "sessions" / "2026" / "05" / "05"
    day.mkdir(parents=True)
    target = day / f"rollout-x-{tid}.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    res = resolve_session(home=tmp_path, env={"CODEX_THREAD_ID": tid})
    assert res.path == target
    assert res.backend == "codex"


def test_resolver_codex_thread_id_set_but_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(NoSessionFound):
        resolve_session(home=tmp_path,
                        env={"CODEX_THREAD_ID": "deadbeef"})


def test_resolver_uses_hook_tmpfile_for_claude(tmp_path: Path) -> None:
    transcript = tmp_path / "claude.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    cache = tmp_path / session_resolver.CACHE_SUBDIR
    cache.mkdir(parents=True)
    (cache / "12345.txt").write_text(str(transcript), encoding="utf-8")

    res = resolve_session(home=tmp_path, ppid=12345, env={})
    assert res.path == transcript
    assert res.backend == "claude"


def test_resolver_falls_back_to_newest_in_cwd_slug(
    tmp_path: Path, capsys
) -> None:
    cwd = "/tmp/myproj"
    slug_dir = tmp_path / ".claude" / "projects" / "-tmp-myproj"
    slug_dir.mkdir(parents=True)
    older = slug_dir / "older.jsonl"
    newer = slug_dir / "newer.jsonl"
    older.write_text("{}\n", encoding="utf-8")
    newer.write_text("{}\n", encoding="utf-8")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    res = resolve_session(home=tmp_path, cwd=cwd, ppid=99999, env={})
    assert res.path == newer
    assert res.backend == "claude"
    # Resolver itself is pure: warning is in the structure, not stderr.
    assert res.fallback_warning is not None
    assert "falling back" in res.fallback_warning.lower()
    assert capsys.readouterr().err == ""


def test_resolver_no_match_anywhere_raises(tmp_path: Path) -> None:
    with pytest.raises(NoSessionFound):
        resolve_session(home=tmp_path, cwd="/nonexistent",
                        ppid=99999, env={})


# --- extract command (mocked provider) ---------------------------------------

class _FakeCompletion:
    def __init__(self, text: str = "session summary", tokens: int = 88,
                 elapsed_ms: int = 17) -> None:
        self.text = text
        self.output_tokens = tokens
        self.elapsed_ms = elapsed_ms


@pytest.fixture
def fake_provider(monkeypatch):
    captured: dict[str, str] = {}

    def fake_call(cfg, prompt: str):
        captured["prompt"] = prompt
        captured["model"] = cfg.provider.model
        return _FakeCompletion()

    monkeypatch.setattr(
        "cheap_llm.commands.extract.call_provider", fake_call
    )
    return captured


def test_extract_happy_path_emits_summary_and_telemetry(
    tmp_config, fake_provider, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question="what was decided?",
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_OK

    out = capsys.readouterr()
    assert "session summary" in out.out
    assert "[cheap]" in out.err
    assert "cmd=extract" in out.err
    assert "backend=explicit" in out.err
    # Question goes into the prompt verbatim.
    assert "what was decided?" in fake_provider["prompt"]
    # Transcript content is rendered.
    assert "[USER]" in fake_provider["prompt"]
    assert "JWT" in fake_provider["prompt"]


def test_extract_messages_only_drops_tool_events(
    tmp_config, fake_provider, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question=None,
        mode="messages-only",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_OK
    prompt = fake_provider["prompt"]
    assert "[TOOL_USE" not in prompt
    assert "[TOOL_RESULT" not in prompt
    # Real chat turns survive.
    assert "[USER]" in prompt
    assert "[ASSISTANT]" in prompt


def test_extract_tail_n_keeps_only_last_messages(
    tmp_config, fake_provider, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question=None,
        mode="full",
        tail=2,
    )
    assert rc == extract_cmd.EXIT_OK
    prompt = fake_provider["prompt"]
    # Last 2 entries in the fixture are: user "And how are passwords hashed?"
    # and assistant "bcrypt with 12 rounds...". So bcrypt MUST be there,
    # but the earlier JWT line MUST NOT.
    assert "bcrypt" in prompt
    assert "JWT" not in prompt


def test_extract_unknown_mode_returns_generic_error(
    tmp_config, fake_provider, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question=None,
        mode="bogus",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_GENERIC_ERROR
    assert "unknown --mode" in capsys.readouterr().err


def test_extract_no_session_returns_dedicated_exit(
    tmp_config, fake_provider, monkeypatch, capsys, tmp_path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(tmp_path / "missing.jsonl"),
        session_id=None,
        question=None,
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_NO_SESSION
    assert "does not exist" in capsys.readouterr().err


def test_extract_codex_fixture_works_too(
    tmp_config, fake_provider, monkeypatch
) -> None:
    """Auto-detect should pick codex parser, command should still work."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CODEX_FX),
        session_id=None,
        question=None,
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_OK
    assert "JWT" in fake_provider["prompt"]


def test_extract_prompt_uses_dense_resumption_template(
    tmp_config, fake_provider, monkeypatch
) -> None:
    """The prompt sent to the cheap provider must:
    - declare the 6-section resumption structure (Mission/Decisions/
      Files/State/Open/Gotchas);
    - forbid invention with "(unknown from transcript)" guard;
    - frame the user's `-q` as a section-weight focus, not a replacer.

    Locking these makes a regression to a generic-summary template
    impossible without a deliberate test edit.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question="what about auth?",
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_OK
    prompt = fake_provider["prompt"]

    for marker in ("### Mission", "### Decisions", "### Files",
                   "### State", "### Open", "### Gotchas"):
        assert marker in prompt, f"missing section marker: {marker}"

    assert "Never invent" in prompt
    assert "(unknown from transcript)" in prompt
    assert "weights sections, does not replace structure" in prompt
    assert "what about auth?" in prompt


def test_extract_provider_error_propagates(
    tmp_config, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    def boom(cfg, prompt):
        raise RuntimeError("network down")

    monkeypatch.setattr("cheap_llm.commands.extract.call_provider", boom)
    rc = extract_cmd.run(
        jsonl=str(CLAUDE_FX),
        session_id=None,
        question=None,
        mode="full",
        tail=None,
    )
    assert rc == extract_cmd.EXIT_PROVIDER_ERROR
    assert "provider call failed" in capsys.readouterr().err
