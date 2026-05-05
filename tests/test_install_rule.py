"""Tests for `cheap install-claude-rule` (Phase-1 alias) and the
generalised `cheap install-rule` — multi-target installer.

The legacy alias is kept stable for back-compat, so its tests stay
unchanged. The new tests at the bottom exercise the multi-target
behaviour: claude / codex / all / auto-detect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cheap_llm.commands import install_claude_rule as install_cmd
from cheap_llm.commands import install_rule as install_rule_cmd


def test_install_creates_file_when_missing(tmp_path: Path, capsys) -> None:
    target = tmp_path / "CLAUDE.md"
    rc = install_cmd.run(force=False, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "Cheap LLM Delegation" in text
    assert "Default Flip" in text
    err = capsys.readouterr().err
    assert "installed: created" in err


def test_install_appends_when_section_absent(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Header\n\n## Other\n\nSomething.\n", encoding="utf-8")
    rc = install_cmd.run(force=False, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "## Other" in text
    assert "Something." in text
    assert "Cheap LLM Delegation" in text
    assert "Default Flip" in text


def test_install_is_idempotent_when_section_present(
    tmp_path: Path, capsys
) -> None:
    target = tmp_path / "CLAUDE.md"
    install_cmd.run(force=False, target=target)
    capsys.readouterr()  # discard first message
    before = target.read_text(encoding="utf-8")
    rc = install_cmd.run(force=False, target=target)
    after = target.read_text(encoding="utf-8")
    assert rc == install_cmd.EXIT_OK
    assert before == after
    err = capsys.readouterr().err
    assert "already installed" in err


def test_force_overwrites_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        "## Cheap LLM delegation\n\nold content\n\n## After\n\nkept.\n",
        encoding="utf-8",
    )
    rc = install_cmd.run(force=True, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "old content" not in text
    assert "Default Flip" in text
    assert "## After" in text
    assert "kept." in text
    # Blank line preserved between our snippet and the next section.
    assert "\n\n## After" in text


def test_force_replaces_block_when_last_section(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        "# Top\n\n## Cheap LLM delegation\n\nold body\n", encoding="utf-8"
    )
    rc = install_cmd.run(force=True, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "old body" not in text
    assert "Default Flip" in text
    assert text.startswith("# Top")


def test_recognises_legacy_lowercase_heading_no_duplicate(
    tmp_path: Path, capsys
) -> None:
    """A pre-existing lowercase legacy heading must be recognised — no second
    copy of the section appended on a plain (no --force) re-install."""
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        "# Top\n\n## Cheap LLM delegation\n\nlegacy body\n", encoding="utf-8"
    )
    rc = install_cmd.run(force=False, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    # Heading recognised → no second "## Cheap LLM …" block written.
    assert text.count("## Cheap LLM") == 1
    # Without --force the legacy body is preserved verbatim.
    assert "legacy body" in text
    err = capsys.readouterr().err
    assert "already installed" in err


def test_force_replaces_legacy_lowercase_heading(tmp_path: Path) -> None:
    """--force on a legacy heading replaces the whole block with the
    current snippet (and its current heading)."""
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        "## Cheap LLM delegation\n\nlegacy body\n", encoding="utf-8"
    )
    rc = install_cmd.run(force=True, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "legacy body" not in text
    assert text.count("## Cheap LLM") == 1
    assert "Default Flip" in text


# --- multi-target install_rule ----------------------------------------------

def test_resolve_targets_claude_only(tmp_path: Path) -> None:
    paths = install_rule_cmd.resolve_targets("claude", home=tmp_path)
    assert paths == [tmp_path / ".claude" / "CLAUDE.md"]


def test_resolve_targets_codex_only(tmp_path: Path) -> None:
    paths = install_rule_cmd.resolve_targets("codex", home=tmp_path)
    assert paths == [tmp_path / ".codex" / "AGENTS.md"]


def test_resolve_targets_all(tmp_path: Path) -> None:
    paths = install_rule_cmd.resolve_targets("all", home=tmp_path)
    assert paths == [
        tmp_path / ".claude" / "CLAUDE.md",
        tmp_path / ".codex" / "AGENTS.md",
    ]


def test_resolve_targets_auto_detects_both(tmp_path: Path) -> None:
    """Both agent dirs present → install into both."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".codex").mkdir()
    paths = install_rule_cmd.resolve_targets("auto", home=tmp_path)
    assert tmp_path / ".claude" / "CLAUDE.md" in paths
    assert tmp_path / ".codex" / "AGENTS.md" in paths


def test_resolve_targets_auto_only_claude(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    paths = install_rule_cmd.resolve_targets("auto", home=tmp_path)
    assert paths == [tmp_path / ".claude" / "CLAUDE.md"]


def test_resolve_targets_auto_only_codex(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir()
    paths = install_rule_cmd.resolve_targets("auto", home=tmp_path)
    assert paths == [tmp_path / ".codex" / "AGENTS.md"]


def test_resolve_targets_auto_falls_back_to_claude_when_neither_present(
    tmp_path: Path,
) -> None:
    """Bootstrap behaviour on a fresh machine — never returns empty list."""
    paths = install_rule_cmd.resolve_targets("auto", home=tmp_path)
    assert paths == [tmp_path / ".claude" / "CLAUDE.md"]


def test_resolve_targets_invalid_value_raises() -> None:
    with pytest.raises(ValueError, match="invalid --target"):
        install_rule_cmd.resolve_targets("bogus")


def test_install_rule_writes_to_codex_agents_md(tmp_path: Path, capsys) -> None:
    """`cheap install-rule --target codex` puts the snippet into AGENTS.md."""
    rc = install_rule_cmd.run(target="codex", home=tmp_path)
    assert rc == install_rule_cmd.EXIT_OK
    target = tmp_path / ".codex" / "AGENTS.md"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "Cheap LLM Delegation" in text
    assert "Default Flip" in text
    err = capsys.readouterr().err
    assert "installed: created" in err
    assert str(target) in err


def test_install_rule_target_all_writes_to_both(tmp_path: Path) -> None:
    rc = install_rule_cmd.run(target="all", home=tmp_path)
    assert rc == install_rule_cmd.EXIT_OK
    claude = (tmp_path / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    codex = (tmp_path / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    assert "Default Flip" in claude
    assert "Default Flip" in codex


def test_install_rule_auto_with_both_dirs_writes_to_both(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".codex").mkdir()
    rc = install_rule_cmd.run(target="auto", home=tmp_path)
    assert rc == install_rule_cmd.EXIT_OK
    assert (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert (tmp_path / ".codex" / "AGENTS.md").exists()


def test_install_rule_invalid_target_returns_error(tmp_path: Path, capsys) -> None:
    rc = install_rule_cmd.run(target="not-a-target", home=tmp_path)
    assert rc == install_rule_cmd.EXIT_GENERIC_ERROR
    assert "invalid --target" in capsys.readouterr().err


def test_install_rule_force_replaces_in_codex_agents_md(tmp_path: Path) -> None:
    """--force must work for the codex target the same way as for claude."""
    target = tmp_path / ".codex" / "AGENTS.md"
    target.parent.mkdir()
    target.write_text(
        "## Cheap LLM Delegation — old body\n\nstale\n", encoding="utf-8"
    )
    rc = install_rule_cmd.run(target="codex", force=True, home=tmp_path)
    assert rc == install_rule_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "stale" not in text
    assert "Default Flip" in text
    assert text.count("## Cheap LLM") == 1
