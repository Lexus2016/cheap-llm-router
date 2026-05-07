"""Tests for ``cheap_llm.__version__`` and ``cheap version`` command."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from cheap_llm import RULE_TEMPLATE_VERSION, __version__
from cheap_llm.cli import app

_PEP440_LOOSE = re.compile(r"^\d+\.\d+\.\d+([+\-].+)?$")


def test_package_exposes_version() -> None:
    assert isinstance(__version__, str) and __version__
    assert _PEP440_LOOSE.match(__version__), f"unexpected: {__version__!r}"


def test_rule_template_version_is_int_and_current() -> None:
    assert isinstance(RULE_TEMPLATE_VERSION, int)
    assert RULE_TEMPLATE_VERSION >= 3


def test_cheap_version_long_form() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    assert "cheap-llm-router" in out
    assert __version__ in out
    assert f"v={RULE_TEMPLATE_VERSION}" in out


def test_cheap_version_short_form() -> None:
    result = CliRunner().invoke(app, ["version", "--short"])
    assert result.exit_code == 0, result.stdout
    assert result.stdout.strip() == __version__
