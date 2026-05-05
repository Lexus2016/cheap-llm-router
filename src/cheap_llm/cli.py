"""Typer CLI dispatcher for ``cheap``."""

from __future__ import annotations

import os
from typing import Optional

import typer

from . import config as config_mod
from .commands import read as read_cmd
from .commands import install_claude_rule as install_cmd

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Delegate read-for-context summaries to a cheap LLM.")
config_app = typer.Typer(no_args_is_help=True, help="Inspect and validate config.")
app.add_typer(config_app, name="config")


@app.command("read")
def cmd_read(
    files: list[str] = typer.Argument(..., help="Files to summarise."),
    question: Optional[str] = typer.Option(
        None, "-q", "--question",
        help="Focus the summary on this question; defaults to a structural overview.",
    ),
    include_sensitive: bool = typer.Option(
        False, "--include-sensitive",
        help="Override the secrets guard (writes a stderr warning).",
    ),
) -> None:
    """Summarise FILE(s) into a short markdown brief and print to stdout."""
    rc = read_cmd.run(files=files, question=question, include_sensitive=include_sensitive)
    raise typer.Exit(rc)


@config_app.command("path")
def cmd_config_path() -> None:
    """Print the resolved config path (creates default if missing)."""
    p = config_mod.ensure_config()
    typer.echo(str(p))


@config_app.command("show")
def cmd_config_show() -> None:
    """Print the raw config — never substitutes env vars or prints API keys."""
    p = config_mod.ensure_config()
    typer.echo(p.read_text(encoding="utf-8"))


@config_app.command("check")
def cmd_config_check() -> None:
    """Validate provider env vars are set; print OK or which is missing."""
    cfg = config_mod.load_config()
    val = os.environ.get(cfg.provider.api_key_env)
    if val:
        typer.echo("OK")
        raise typer.Exit(0)
    typer.echo(f"missing env: {cfg.provider.api_key_env}", err=True)
    raise typer.Exit(2)


@app.command("install-claude-rule")
def cmd_install_claude_rule(
    force: bool = typer.Option(
        False, "--force",
        help="Overwrite the existing block if present.",
    ),
) -> None:
    """Idempotently install the ## Cheap LLM delegation rule into ~/.claude/CLAUDE.md."""
    rc = install_cmd.run(force=force)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
