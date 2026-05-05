"""Configuration loader for cheap-llm-router.

Resolves ~/.config/cheap-llm/config.yaml (XDG), auto-creating it from
the embedded default template on first invocation. Provides a
SafeFormatDict whose ``__missing__`` preserves unknown ``{key}``
placeholders so user-edited prompt templates do not raise KeyError.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG = """\
provider:
  base_url: https://openrouter.ai/api/v1
  # Pick exactly ONE of the two below.
  # `api_key_env` is safer: name a shell env var, keep the real key out
  # of dotfiles, screenshots, and backups.
  # `api_key` (literal) is supported for setups where exporting an env
  # var is inconvenient — but then this YAML file holds a secret. Keep
  # it out of git, iCloud/Dropbox sync, screenshots. `cheap config show`
  # redacts this field automatically, but `cat config.yaml` does not.
  api_key_env: OPENROUTER_API_KEY
  # api_key: sk-or-v1-...
  model: deepseek/deepseek-v4-pro
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
    # Exactly one of these is expected to carry the credential:
    # `api_key_env` is the shell-env-var name (preferred); `api_key` is
    # the literal token (only when env is not workable in your setup).
    api_key_env: str | None
    api_key: str | None
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
            api_key_env=prov.get("api_key_env"),
            api_key=prov.get("api_key"),
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
    """Return the api key value, or None if not configured.

    Priority: explicit ``api_key`` (literal in config) > ``api_key_env``
    (env-var lookup) > None. Never logged or printed by this function.
    """
    if cfg.provider.api_key:
        return cfg.provider.api_key
    if cfg.provider.api_key_env:
        return os.environ.get(cfg.provider.api_key_env)
    return None


_SECRET_PREFIXES = ("sk-", "Bearer ", "ghp_", "gho_", "github_pat_")


def looks_like_secret(value: str) -> bool:
    """Heuristic: True if a string looks like a token rather than an env-var name.

    Used by `cheap config check` to avoid echoing values that might be
    secrets (e.g. when a literal key got pasted into ``api_key_env`` by
    mistake), and by ``redact_secrets`` for ``cheap config show``.
    Conservative on purpose: false positives are fine (we just print
    less); false negatives leak.
    """
    if not value:
        return False
    if value.startswith(_SECRET_PREFIXES):
        return True
    if len(value) > 40 and " " not in value and any(c.isdigit() for c in value):
        return True
    return False


# Matches `api_key:` lines in YAML, capturing the value (quoted or bare).
# Used to redact `cheap config show` output.
_API_KEY_LINE_RE = re.compile(
    r'^(\s*api_key\s*:\s*)(["\']?)([^\n"\']*)\2\s*$',
    re.MULTILINE,
)


def redact_secrets(yaml_text: str) -> str:
    """Replace any `api_key:` value in YAML text with a redacted marker.

    `api_key_env:` is left intact (it's the var NAME, not a secret),
    unless the value itself looks like a token (mistaken paste); in that
    case we redact too.
    """
    out = _API_KEY_LINE_RE.sub(
        lambda m: f'{m.group(1)}"***REDACTED***"',
        yaml_text,
    )
    # Also defang api_key_env values that look like a literal secret,
    # so a misconfigured file does not leak via `config show`.
    def _maybe_redact_env_line(m: "re.Match[str]") -> str:
        prefix, q, value = m.group(1), m.group(2), m.group(3)
        if looks_like_secret(value):
            return f'{prefix}"***REDACTED (looks like a literal key — move to api_key field)***"'
        return m.group(0)

    out = re.sub(
        r'^(\s*api_key_env\s*:\s*)(["\']?)([^\n"\']*)\2\s*$',
        _maybe_redact_env_line,
        out,
        flags=re.MULTILINE,
    )
    return out


class SafeFormatDict(dict):
    """``str.format_map`` helper: missing keys round-trip as ``{key}``.

    Lets users edit ``prompt_template`` and include literal ``{...}``
    text without raising ``KeyError``.
    """

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return "{" + key + "}"
