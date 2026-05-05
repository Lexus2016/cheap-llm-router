"""Unit tests for cheap_llm.commands.read with mocked provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from cheap_llm.commands import read as read_cmd


class FakeCompletion:
    def __init__(self, text: str = "summary text", tokens: int = 42,
                 elapsed_ms: int = 12) -> None:
        self.text = text
        self.output_tokens = tokens
        self.elapsed_ms = elapsed_ms


@pytest.fixture
def fake_provider(monkeypatch):
    captured: dict[str, str] = {}

    def fake_call(cfg, prompt: str):
        captured["prompt"] = prompt
        captured["model"] = cfg.provider.model
        return FakeCompletion()

    monkeypatch.setattr("cheap_llm.commands.read.call_provider", fake_call)
    return captured


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_run_happy_path_emits_summary_and_telemetry(
    tmp_config, tmp_path: Path, fake_provider, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    f1 = _write(tmp_path, "a.py", "def alpha(): pass\n")
    f2 = _write(tmp_path, "b.py", "def beta(): pass\n")

    rc = read_cmd.run(files=[str(f1), str(f2)], question="explain",
                      include_sensitive=False)
    assert rc == read_cmd.EXIT_OK

    out = capsys.readouterr()
    assert "summary text" in out.out
    assert "[cheap]" in out.err
    assert "files=2" in out.err
    assert "output_tokens=42" in out.err
    assert "model=moonshotai/kimi-k2" in out.err

    assert "explain" in fake_provider["prompt"]
    assert "--- FILE:" in fake_provider["prompt"]
    assert "def alpha" in fake_provider["prompt"]


def test_run_uses_overview_when_question_missing(
    tmp_config, tmp_path: Path, fake_provider, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    f1 = _write(tmp_path, "a.py", "def x(): pass\n")
    rc = read_cmd.run(files=[str(f1)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_OK
    assert "general structural overview" in fake_provider["prompt"]


def test_run_fails_fast_when_file_missing(
    tmp_config, tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    rc = read_cmd.run(files=[str(tmp_path / "nope.py")], question=None,
                      include_sensitive=False)
    assert rc == read_cmd.EXIT_GENERIC_ERROR
    assert "not found" in capsys.readouterr().err


def test_run_oversized_input_rejected(
    tmp_config, tmp_path: Path, monkeypatch, capsys
) -> None:
    """Concat > max_input_chars must exit with EXIT_OVERSIZED."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    big = _write(tmp_path, "huge.py", "x" * (400_001))
    rc = read_cmd.run(files=[str(big)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_OVERSIZED
    assert "exceeds" in capsys.readouterr().err


def test_run_provider_error_propagates(
    tmp_config, tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    f1 = _write(tmp_path, "a.py", "x")

    def boom(cfg, prompt):
        raise RuntimeError("network down")

    monkeypatch.setattr("cheap_llm.commands.read.call_provider", boom)
    rc = read_cmd.run(files=[str(f1)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_PROVIDER_ERROR
    assert "provider call failed" in capsys.readouterr().err


def test_run_missing_api_key_returns_provider_error(
    tmp_config, tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    f1 = _write(tmp_path, "a.py", "x")

    # Real call_provider used; should raise MissingApiKey.
    rc = read_cmd.run(files=[str(f1)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_PROVIDER_ERROR
    err = capsys.readouterr().err
    assert "OPENROUTER_API_KEY" in err
