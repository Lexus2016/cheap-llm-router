"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch) -> Path:
    """Redirect XDG_CONFIG_HOME so config writes land in a tmp dir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return tmp_path / "xdg" / "cheap-llm" / "config.yaml"


@pytest.fixture(autouse=True)
def _isolate_usage_log(monkeypatch, tmp_path_factory, request) -> Path | None:
    """Send usage_log.record() into a per-test tmp file.

    Without this, every pytest run that goes through `read.run` /
    `extract.run` (with a mocked provider) writes a real entry into
    the user's ``~/.cache/cheap-llm/usage.log``, polluting the
    adoption-measurement signal we built that file to provide.

    Skipped for `test_usage_log.py` itself, because that file's tests
    *are* the ones that exercise log_path resolution and record() with
    explicit ``path=`` arguments — patching log_path globally there
    would mask the very behaviour under test. The two integration-
    style tests in that file (test_read_records_*, test_extract_records_*)
    install their own monkey-patch, which works correctly without our
    autouse layer.
    """
    if "test_usage_log.py" in str(request.fspath):
        return None
    log_dir = tmp_path_factory.mktemp("cheap-usage")
    log_file = log_dir / "usage.log"
    monkeypatch.setattr("cheap_llm.usage_log.log_path", lambda: log_file)
    return log_file
