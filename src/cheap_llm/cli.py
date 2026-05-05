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
    """Print the config — `api_key:` is redacted, env-var names left as-is.

    Use `cat $(cheap config path)` if you really need the raw value
    (and you accept that any screenshot of that output leaks the key).
    """
    p = config_mod.ensure_config()
    typer.echo(config_mod.redact_secrets(p.read_text(encoding="utf-8")))


@config_app.command("check")
def cmd_config_check() -> None:
    """Validate provider credentials are reachable; print OK or what's missing.

    Never echoes a value that could itself be a secret.
    """
    cfg = config_mod.load_config()
    if config_mod.resolve_api_key(cfg):
        typer.echo("OK")
        raise typer.Exit(0)

    if cfg.provider.api_key is not None:
        msg = "missing api key (api_key in config is set but empty)"
    else:
        env_name = cfg.provider.api_key_env or ""
        if env_name and not config_mod.looks_like_secret(env_name):
            msg = f"missing env: {env_name}"
        else:
            msg = ("missing api key (api_key_env does not look like an "
                   "env-var name; if you pasted a literal key there, "
                   "move it to the api_key field instead)")
    typer.echo(msg, err=True)
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
