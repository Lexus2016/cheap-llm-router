"""Tests for `cheap install-claude-rule` — idempotency + --force."""

from __future__ import annotations

from pathlib import Path

from cheap_llm.commands import install_claude_rule as install_cmd


def test_install_creates_file_when_missing(tmp_path: Path, capsys) -> None:
    target = tmp_path / "CLAUDE.md"
    rc = install_cmd.run(force=False, target=target)
    assert rc == install_cmd.EXIT_OK
    text = target.read_text(encoding="utf-8")
    assert "Cheap LLM Delegation" in text
    assert "Mandatory Checkpoint" in text
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
    assert "Mandatory Checkpoint" in text


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
    assert "Mandatory Checkpoint" in text
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
    assert "Mandatory Checkpoint" in text
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
    assert "Mandatory Checkpoint" in text
