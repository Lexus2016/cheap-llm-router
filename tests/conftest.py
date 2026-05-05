"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cheap_llm import config as config_mod


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch) -> Path:
    """Redirect XDG_CONFIG_HOME so config writes land in a tmp dir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return tmp_path / "xdg" / "cheap-llm" / "config.yaml"


@pytest.fixture
def loaded_config(tmp_config) -> config_mod.Config:
    return config_mod.load_config()


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MODULE = FIXTURES_DIR / "sample_module"
ENV_FIXTURE = FIXTURES_DIR / ".env.test"


@pytest.fixture
def sample_files() -> list[Path]:
    return sorted(SAMPLE_MODULE.glob("*.py"))
