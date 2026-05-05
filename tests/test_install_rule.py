"""Tests for `cheap install-claude-rule` — idempotency + --force."""

from __future__ import annotations

from pathlib import Path

from cheap_llm.commands import install_claude_rule as install_cmd


def test_install_creates_file_when_missing(tmp_path: Path, capsys) -> None:
    target = tmp_path / "CLAUDE.md"
    rc = install_cmd.run(force=False, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "## Cheap LLM delegation" in text
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
    assert "## Cheap LLM delegation" in text


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
    assert "When reading 3+ files only for context" in text
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
    assert "When reading 3+ files only for context" in text
    assert text.startswith("# Top")
