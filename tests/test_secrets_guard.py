"""Secrets-guard tests — covers acceptance criterion §2.3."""

from __future__ import annotations

from pathlib import Path

import pytest

from cheap_llm import secrets as guard
from cheap_llm.commands import read as read_cmd


def test_find_refused_blocks_dotenv_and_keys(tmp_path: Path) -> None:
    paths = [
        tmp_path / "src.py",
        tmp_path / ".env.test",
        tmp_path / "private.key",
        tmp_path / "id_rsa",
    ]
    for p in paths:
        p.write_text("x")
    refused = guard.find_refused(paths, [".env*", "*.key", "id_rsa"])
    refused_names = {p.name for p in refused}
    assert refused_names == {".env.test", "private.key", "id_rsa"}


def test_find_refused_allows_pub_keys(tmp_path: Path) -> None:
    pub = tmp_path / "id_rsa.pub"
    pub.write_text("ssh-rsa ...")
    assert guard.find_refused([pub], ["id_rsa", "*.key"]) == []


def test_find_refused_uses_basename_only(tmp_path: Path) -> None:
    nested = tmp_path / "cfg" / "credentials.json"
    nested.parent.mkdir()
    nested.write_text("{}")
    assert guard.find_refused([nested], ["credentials.json"]) == [nested]


def test_run_refuses_dotenv_and_does_not_call_provider(
    tmp_config: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    """Acceptance §2.3: .env.test → exit non-zero, provider not called."""
    secret = tmp_path / ".env.test"
    secret.write_text("OPENROUTER_API_KEY=should-not-leak")

    called = {"n": 0}

    def fake_call(*a, **kw):
        called["n"] += 1
        raise AssertionError("provider must not be called for refused files")

    monkeypatch.setattr("cheap_llm.commands.read.call_provider", fake_call)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    rc = read_cmd.run(files=[str(secret)], question=None,
                      include_sensitive=False)
    assert rc == read_cmd.EXIT_SECRETS_REFUSED
    assert called["n"] == 0
    err = capsys.readouterr().err
    assert "refused" in err and ".env.test" in err


def test_run_with_include_sensitive_warns_on_stderr(
    tmp_config: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    """Override flag proceeds but writes a stderr warning naming the file."""
    secret = tmp_path / ".env.test"
    secret.write_text("dummy=1")

    class FakeCompletion:
        text = "summary"
        output_tokens = 10
        elapsed_ms = 5

    monkeypatch.setattr("cheap_llm.commands.read.call_provider",
                        lambda cfg, prompt: FakeCompletion())
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    rc = read_cmd.run(files=[str(secret)], question=None,
                      include_sensitive=True)
    assert rc == read_cmd.EXIT_OK
    err = capsys.readouterr().err
    assert "WARNING --include-sensitive" in err
    assert ".env.test" in err
