"""Provider client wrapper.

Tiny shim over the ``openai`` SDK with ``base_url`` override so any
OpenAI-compatible endpoint (OpenRouter, Moonshot direct, DeepSeek,
Gemini-via-proxy, etc.) works without code changes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI

from .config import Config, resolve_api_key


@dataclass(frozen=True)
class Completion:
    text: str
    output_tokens: int
    elapsed_ms: int


class MissingApiKey(RuntimeError):
    pass


def call_provider(cfg: Config, prompt: str) -> Completion:
    api_key = resolve_api_key(cfg)
    if not api_key:
        raise MissingApiKey(
            f"env var {cfg.provider.api_key_env!r} is not set; run `cheap config check`"
        )

    client = OpenAI(
        base_url=cfg.provider.base_url,
        api_key=api_key,
        timeout=cfg.provider.request_timeout_seconds,
    )

    started = time.monotonic()
    # Send BOTH max_tokens (legacy, all providers) and max_completion_tokens
    # (newer; reasoning-capable models honour only this for the full output
    # including hidden reasoning tokens). Providers that don't recognise
    # max_completion_tokens silently ignore it; for non-reasoning models
    # both params produce the same cap. See evaluation log in README.
    response = client.chat.completions.create(
        model=cfg.provider.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=cfg.provider.temperature,
        max_tokens=cfg.read.max_summary_tokens,
        extra_body={"max_completion_tokens": cfg.read.max_summary_tokens},
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)

    text = response.choices[0].message.content or ""
    output_tokens = (response.usage.completion_tokens
                     if response.usage and response.usage.completion_tokens is not None
                     else 0)
    return Completion(text=text, output_tokens=output_tokens, elapsed_ms=elapsed_ms)
