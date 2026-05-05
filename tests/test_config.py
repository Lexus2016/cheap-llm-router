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
    assert cfg.provider.model == "deepseek/deepseek-v4-pro"
    # Default template uses api_key_env; api_key is None unless user set it.
    assert cfg.provider.api_key_env == "OPENROUTER_API_KEY"
    assert cfg.provider.api_key is None
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


def test_resolve_api_key_prefers_literal_over_env(
    tmp_config: Path, monkeypatch
) -> None:
    """`api_key` (literal in config) wins over `api_key_env` even if env is set."""
    config_mod.ensure_config(tmp_config)  # Materialise the default file first.
    text = tmp_config.read_text(encoding="utf-8")
    text = text.replace(
        "api_key_env: OPENROUTER_API_KEY",
        "api_key_env: OPENROUTER_API_KEY\n  api_key: sk-or-from-config",
    )
    tmp_config.write_text(text, encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-from-env")

    cfg = config_mod.load_config(tmp_config)
    assert cfg.provider.api_key == "sk-or-from-config"
    assert config_mod.resolve_api_key(cfg) == "sk-or-from-config"


def test_looks_like_secret_recognises_tokens_not_names() -> None:
    assert config_mod.looks_like_secret("sk-or-v1-abc123def456")
    assert config_mod.looks_like_secret("sk-ant-abcd1234")
    assert config_mod.looks_like_secret("Bearer abcd1234efgh5678ijkl9012mnop3456qrst")
    assert config_mod.looks_like_secret("ghp_" + "x" * 40)
    # Normal env-var names — must NOT trip.
    assert not config_mod.looks_like_secret("OPENROUTER_API_KEY")
    assert not config_mod.looks_like_secret("MY_API_KEY")
    assert not config_mod.looks_like_secret("ANTHROPIC_API_KEY")
    assert not config_mod.looks_like_secret("")


def test_redact_secrets_masks_api_key_field() -> None:
    yaml_in = (
        "provider:\n"
        "  base_url: https://x\n"
        '  api_key: "sk-or-v1-realsecret"\n'
        "  api_key_env: OPENROUTER_API_KEY\n"
    )
    out = config_mod.redact_secrets(yaml_in)
    assert "sk-or-v1-realsecret" not in out
    assert "REDACTED" in out
    # api_key_env value (a normal name) is preserved as-is.
    assert "OPENROUTER_API_KEY" in out


def test_redact_secrets_flags_secret_pasted_into_api_key_env() -> None:
    """A literal token mistakenly pasted into api_key_env is also masked,
    so `cheap config show` cannot leak it via screenshot."""
    yaml_in = (
        'provider:\n'
        '  api_key_env: "sk-or-v1-pastedhere"\n'
    )
    out = config_mod.redact_secrets(yaml_in)
    assert "sk-or-v1-pastedhere" not in out
    assert "REDACTED" in out
