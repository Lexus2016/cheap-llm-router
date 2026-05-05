"""``cheap extract`` — summarise a Claude/Codex session transcript via a
cheap provider, so a compaction or "what did we do" question does not
burn the expensive subscription on re-reading raw JSONL.

The transcript is auto-detected (Claude Code session JSONL, Codex CLI
rollout JSONL, or generic), normalised to ``Message`` objects, optionally
filtered (mode + tail), rendered into a compact text block, and sent
through the same ``call_provider`` path as ``cheap read``.
"""

from __future__ import annotations

import sys
from typing import Sequence

from .. import transcript as tr
from ..client import MissingApiKey, call_provider
from ..config import Config, SafeFormatDict, load_config
from ..session_resolver import (
    AmbiguousSession,
    NoSessionFound,
    resolve_session,
)


EXIT_OK = 0
EXIT_GENERIC_ERROR = 1
EXIT_NO_SESSION = 5
EXIT_OVERSIZED = 3
EXIT_PROVIDER_ERROR = 4


_DEFAULT_QUESTION = "(general session summary — what was done, decisions, open threads)"


_PROMPT_TEMPLATE = """\
You are a session-log summarizer. Read the transcript below (a chat
history between a developer and an AI coding assistant) and produce a
factual summary focused on: what was attempted, what decisions were
made, which files were touched, and any open threads or unfinished
work. Skip small-talk and tool-output noise. Aim for ~{max_summary_tokens}
tokens.

Focus: {question_or_overview}

Transcript ({backend}, {n_messages} messages):
{transcript_block}
"""


def _err(msg: str) -> None:
    print(f"cheap extract: error: {msg}", file=sys.stderr)


def _telemetry(*, backend: str, n_messages: int, input_chars: int,
               output_tokens: int, model: str, elapsed_ms: int) -> None:
    print(
        f"[cheap] cmd=extract backend={backend} messages={n_messages} "
        f"input_chars={input_chars} output_tokens={output_tokens} "
        f"model={model} elapsed_ms={elapsed_ms}",
        file=sys.stderr,
    )


def run(
    *,
    jsonl: str | None,
    session_id: str | None,
    question: str | None,
    mode: "tr.Mode | str",
    tail: int | None,
    cfg: Config | None = None,
) -> int:
    cfg = cfg or load_config()

    # 1. resolve which transcript file is "ours"
    try:
        resolved = resolve_session(jsonl=jsonl, session_id=session_id)
    except (NoSessionFound, AmbiguousSession) as e:
        _err(str(e))
        return EXIT_NO_SESSION
    if resolved.fallback_warning:
        print(f"cheap extract: WARNING {resolved.fallback_warning}", file=sys.stderr)

    # 2. parse with the format-appropriate backend
    parser = tr.detect_format(resolved.path)
    messages = list(parser(resolved.path))

    # 3. mode filter + tail
    try:
        mode_enum = tr.Mode(mode)
    except ValueError:
        _err(f"unknown --mode {mode!r}; pick one of: full, messages-only")
        return EXIT_GENERIC_ERROR
    messages = list(tr.filter_mode(iter(messages), mode_enum))
    messages = tr.take_tail(messages, tail)

    if not messages:
        _err(
            f"transcript {resolved.path} contains no messages after mode/tail "
            f"filtering. Try --mode full or a larger --tail."
        )
        return EXIT_GENERIC_ERROR

    # 4. render → prompt
    transcript_block = tr.render_for_prompt(messages)
    if len(transcript_block) > cfg.read.max_input_chars:
        _err(
            f"rendered transcript ({len(transcript_block)} chars) exceeds "
            f"max_input_chars={cfg.read.max_input_chars}. Use --tail N to "
            f"trim, or raise the cap in config."
        )
        return EXIT_OVERSIZED

    template_vars = SafeFormatDict({
        "max_summary_tokens": cfg.read.max_summary_tokens,
        "question_or_overview": question or _DEFAULT_QUESTION,
        "backend": resolved.backend,
        "n_messages": len(messages),
        "transcript_block": transcript_block,
    })
    prompt = _PROMPT_TEMPLATE.format_map(template_vars)

    # 5. provider call
    try:
        completion = call_provider(cfg, prompt)
    except MissingApiKey as e:
        _err(str(e))
        return EXIT_PROVIDER_ERROR
    except Exception as e:  # provider/network error
        _err(f"provider call failed: {e}")
        return EXIT_PROVIDER_ERROR

    # 6. write summary to stdout, telemetry to stderr
    sys.stdout.write(completion.text)
    if not completion.text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()

    _telemetry(
        backend=resolved.backend,
        n_messages=len(messages),
        input_chars=len(transcript_block),
        output_tokens=completion.output_tokens,
        model=cfg.provider.model,
        elapsed_ms=completion.elapsed_ms,
    )
    return EXIT_OK
