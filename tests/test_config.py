"""Config loader tests."""

from __future__ import annotations

from pathlib import Path

from cheap_llm import config as config_mod


def test_ensure_config_creates_default(tmp_config: Path, capsys) -> None:
    assert not tmp_config.exists()
    out = config_mod.ensure_config(tmp_config)
    assert out == tmp_config
    assert tmp_config.exists()
    err = capsys.readouterr().err
    assert "created default config" in err


def test_ensure_config_is_idempotent(tmp_config: Path) -> None:
    first = config_mod.ensure_config(tmp_config)
    mtime_before = first.stat().st_mtime_ns
    second = config_mod.ensure_config(tmp_config)
    assert second == first
    assert second.stat().st_mtime_ns == mtime_before


def test_load_config_returns_typed_dataclass(tmp_config: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_config.parent.parent))
    cfg = config_mod.load_config(tmp_config)
    assert cfg.provider.base_url.startswith("https://openrouter.ai")
    assert cfg.provider.model == "moonshotai/kimi-k2"
    assert cfg.read.max_summary_tokens == 600
    assert ".env*" in cfg.secrets_patterns
    assert "id_rsa" in cfg.secrets_patterns
    assert "*.pub" not in cfg.secrets_patterns


def test_safe_format_dict_preserves_unknown_keys() -> None:
    d = config_mod.SafeFormatDict({"a": "1"})
    out = "{a} and {unknown}".format_map(d)
    assert out == "1 and {unknown}"


def test_resolve_api_key_returns_env_value(tmp_config: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
    cfg = config_mod.load_config(tmp_config)
    assert config_mod.resolve_api_key(cfg) == "sk-test-123"


def test_resolve_api_key_returns_none_when_missing(tmp_config: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cfg = config_mod.load_config(tmp_config)
    assert config_mod.resolve_api_key(cfg) is None
