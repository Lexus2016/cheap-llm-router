"""Configuration loader for cheap-llm-router.

Resolves ~/.config/cheap-llm/config.yaml (XDG), auto-creating it from
the embedded default template on first invocation. Provides a
SafeFormatDict whose ``__missing__`` preserves unknown ``{key}``
placeholders so user-edited prompt templates do not raise KeyError.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG = """\
provider:
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY
  model: moonshotai/kimi-k2
  temperature: 0.2
  request_timeout_seconds: 60

read:
  max_summary_tokens: 600
  max_input_chars: 400000
  prompt_template: |
    You are a code summarizer. Read the files below and produce a
    factual summary focused on: public API, key data flow, important
    invariants, gotchas. Skip boilerplate. Aim for ~{max_summary_tokens}
    tokens. Use markdown headings per file.

    For every public symbol you mention, cite as `path/to/file.py:LINE`
    so the reader can verify it. Do NOT invent symbols not present in
    the files; omit anything you are unsure about.

    Focus: {question_or_overview}

    Files:
    {files_block}

secrets_guard:
  patterns:
    - ".env*"
    - "*.pem"
    - "*.key"
    - "*.pfx"
    - "credentials.json"
    - "credentials.yaml"
    - "credentials.yml"
    - ".npmrc"
    - ".pypirc"
    - "id_rsa"
    - "id_dsa"
    - "id_ecdsa"
    - "id_ed25519"
"""


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "cheap-llm" / "config.yaml"


def ensure_config(path: Path | None = None) -> Path:
    """Create the default config if missing. Idempotent.

    Returns the resolved path. Prints a one-line stderr notice on creation.
    """
    p = path or config_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"created default config at {p}", file=sys.stderr)
    return p


@dataclass(frozen=True)
class ProviderCfg:
    base_url: str
    api_key_env: str
    model: str
    temperature: float
    request_timeout_seconds: int


@dataclass(frozen=True)
class ReadCfg:
    max_summary_tokens: int
    max_input_chars: int
    prompt_template: str


@dataclass(frozen=True)
class Config:
    provider: ProviderCfg
    read: ReadCfg
    secrets_patterns: tuple[str, ...]


def load_config(path: Path | None = None) -> Config:
    p = ensure_config(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    prov = data.get("provider", {})
    read = data.get("read", {})
    sec = data.get("secrets_guard", {}) or {}

    return Config(
        provider=ProviderCfg(
            base_url=prov["base_url"],
            api_key_env=prov["api_key_env"],
            model=prov["model"],
            temperature=float(prov.get("temperature", 0.2)),
            request_timeout_seconds=int(prov.get("request_timeout_seconds", 60)),
        ),
        read=ReadCfg(
            max_summary_tokens=int(read.get("max_summary_tokens", 600)),
            max_input_chars=int(read.get("max_input_chars", 400_000)),
            prompt_template=read.get("prompt_template") or "",
        ),
        secrets_patterns=tuple(sec.get("patterns") or ()),
    )


def resolve_api_key(cfg: Config) -> str | None:
    """Return the api key value from env, or None if not set.

    Never logged or printed by this function.
    """
    return os.environ.get(cfg.provider.api_key_env)


class SafeFormatDict(dict):
    """``str.format_map`` helper: missing keys round-trip as ``{key}``.

    Lets users edit ``prompt_template`` and include literal ``{...}``
    text without raising ``KeyError``.
    """

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return "{" + key + "}"
