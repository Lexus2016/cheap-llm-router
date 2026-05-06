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
    # Stable across default-model changes: assert telemetry reports
    # the same model the CLI actually used (captured by fake_provider).
    assert f"model={fake_provider['model']}" in out.err

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


def test_run_handles_nested_braces_in_file_content(
    tmp_config, tmp_path: Path, fake_provider, monkeypatch
) -> None:
    """Regression: file content with nested `{...}` (TS template literals,
    JSON, Python f-strings, deep object literals) must NOT trip Python's
    str.format-spec parser into 'Max string recursion exceeded'.

    Trigger: deeply nested braces resembling format specs (`{:{}}` is the
    minimal recursive form). Real-world hits include uncommitted diffs of
    TypeScript code, JSON config, and Python f-strings — anything where
    one or more files contain things the format parser would interpret.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    nasty = (
        "const config = { foo: { bar: `${baz}` }, items: ["
        "{ a: 1 }, { b: 2 }, { c: { d: { e: 3 } } }] };\n"
        "// Python lookalike: {:{}} {0:{1}} {x!r:{w}}\n"
        "// Repeated to push past format-parser recursion limits:\n"
        + "{ foo: { bar: { baz: { qux: { quux: 1 } } } } }\n" * 50
    )
    f1 = _write(tmp_path, "diff.ts", nasty)
    rc = read_cmd.run(files=[str(f1)], question="explain",
                      include_sensitive=False)
    assert rc == read_cmd.EXIT_OK
    # Sanity: nasty content survived intact into the prompt — i.e. we
    # didn't accidentally interpret it as format placeholders.
    assert "${baz}" in fake_provider["prompt"]
    assert "{:{}}" in fake_provider["prompt"]


def test_run_handles_nested_format_specs_in_custom_template(
    tmp_config, tmp_path: Path, fake_provider, monkeypatch
) -> None:
    """The actual `format_map` recursion bug: a user-customised
    `prompt_template` with nested colons inside braces (a typo, a TS
    type signature accidentally pasted in, etc.) USED to crash with
    'Max string recursion exceeded' because Python's format-spec parser
    recurses on `{name:{spec}}` and bombs at depth ~2.

    The previous two tests prove nested braces in VALUES pass through
    unchanged — but values never triggered the bug. This test exercises
    the actual buggy path: nasty syntax in the TEMPLATE itself. With
    `.replace()` we don't parse spec syntax at all, so this is safe.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    f1 = _write(tmp_path, "x.py", "def x(): pass\n")

    # Patch the loaded cfg's prompt_template to a nasty string. This is
    # the shape that crashed `cheap read` when users hand-edited their
    # ~/.config/cheap-llm/config.yaml or accidentally introduced TS-like
    # syntax into the template.
    from cheap_llm.config import load_config
    cfg = load_config()
    nasty_template = (
        "Files:\n{files_block}\n"
        "DO NOT use this syntax: {a:{b:{c:{d:{e:{f:{g:{h:{i:1}}}}}}}}}\n"
        "Aim for ~{max_summary_tokens} tokens. Focus: {question_or_overview}"
    )
    object.__setattr__(cfg.read, "prompt_template", nasty_template)

    rc = read_cmd.run(files=[str(f1)], question="explain",
                      include_sensitive=False, cfg=cfg)
    assert rc == read_cmd.EXIT_OK
    # The nasty pattern survives verbatim into the prompt — we substitute
    # only our 3 known placeholders, never parse format specs.
    assert "{a:{b:{c:{d:{e:{f:{g:{h:{i:1}}}}}}}}}" in fake_provider["prompt"]


def test_run_handles_literal_brace_placeholders_in_file_content(
    tmp_config, tmp_path: Path, fake_provider, monkeypatch
) -> None:
    """A file containing `{max_summary_tokens}` literally must NOT have
    that text accidentally substituted: only the template's placeholders
    get replaced, never arbitrary text in user files.

    Regression guard for the order of `.replace()` calls in `run`: if
    `files_block` is interpolated BEFORE the other placeholders, the
    file's literal `{max_summary_tokens}` would get substituted with
    the cap value, silently corrupting the user's content.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    body = "doc says: cap is {max_summary_tokens} tokens.\n"
    f1 = _write(tmp_path, "doc.md", body)
    rc = read_cmd.run(files=[str(f1)], question=None, include_sensitive=False)
    assert rc == read_cmd.EXIT_OK
    prompt = fake_provider["prompt"]
    # The file's literal `{max_summary_tokens}` text must survive verbatim.
    # If the order were wrong (files_block first, then other placeholders),
    # this assertion would fail because the brace would be substituted away.
    assert "doc says: cap is {max_summary_tokens} tokens." in prompt


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
