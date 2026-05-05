"""``cheap read`` — summarise a list of files via a cheap provider."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from ..config import Config, SafeFormatDict, load_config
from ..secrets import find_refused
from ..client import call_provider, MissingApiKey

EXIT_OK = 0
EXIT_GENERIC_ERROR = 1
EXIT_SECRETS_REFUSED = 2
EXIT_OVERSIZED = 3
EXIT_PROVIDER_ERROR = 4

_NO_QUESTION = "(general structural overview — no specific question)"


class _ReadFileError(ValueError):
    """Raised by _read_files for a non-utf-8 / unreadable file.

    Subclass of ValueError so callers can catch it specifically and
    surface a structured EXIT_GENERIC_ERROR instead of crashing with
    SystemExit (which Python prints separately).
    """


def _read_files(paths: Sequence[Path]) -> str:
    chunks: list[str] = []
    for p in paths:
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise _ReadFileError(
                f"binary file or non-utf-8 content: {p} ({e})"
            ) from e
        except OSError as e:
            raise _ReadFileError(f"cannot read {p}: {e}") from e
        chunks.append(f"--- FILE: {p} ---\n{content}")
    return "\n\n".join(chunks)


def _err(msg: str) -> str:
    print(f"cheap read: error: {msg}", file=sys.stderr)
    return msg


def _telemetry(*, files: int, input_chars: int, output_tokens: int,
               model: str, elapsed_ms: int) -> None:
    print(
        f"[cheap] files={files} input_chars={input_chars} "
        f"output_tokens={output_tokens} model={model} elapsed_ms={elapsed_ms}",
        file=sys.stderr,
    )


def run(files: Sequence[str], question: str | None,
        include_sensitive: bool, cfg: Config | None = None) -> int:
    cfg = cfg or load_config()

    paths = [Path(f) for f in files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        _err(f"file(s) not found: {', '.join(str(p) for p in missing)}")
        return EXIT_GENERIC_ERROR
    if not paths:
        _err("no files given")
        return EXIT_GENERIC_ERROR

    refused = find_refused(paths, cfg.secrets_patterns)
    if refused and not include_sensitive:
        names = ", ".join(str(p) for p in refused)
        _err(
            f"refused (matches secrets_guard.patterns): {names}. "
            "If you really mean it, re-run with --include-sensitive "
            "(but read the rule in ~/.claude/CLAUDE.md first)."
        )
        return EXIT_SECRETS_REFUSED
    if refused and include_sensitive:
        names = ", ".join(str(p) for p in refused)
        print(
            f"cheap read: WARNING --include-sensitive bypassed guard for: {names}",
            file=sys.stderr,
        )

    try:
        files_block = _read_files(paths)
    except _ReadFileError as e:
        _err(str(e))
        return EXIT_GENERIC_ERROR

    if len(files_block) > cfg.read.max_input_chars:
        _err(
            f"concatenated input ({len(files_block)} chars) exceeds "
            f"max_input_chars={cfg.read.max_input_chars}. "
            "Pass fewer files or raise the cap in config."
        )
        return EXIT_OVERSIZED

    template_vars = SafeFormatDict({
        "max_summary_tokens": cfg.read.max_summary_tokens,
        "question_or_overview": question or _NO_QUESTION,
        "files_block": files_block,
    })
    prompt = cfg.read.prompt_template.format_map(template_vars)

    try:
        completion = call_provider(cfg, prompt)
    except MissingApiKey as e:
        _err(str(e))
        return EXIT_PROVIDER_ERROR
    except Exception as e:  # provider/network error
        _err(f"provider call failed: {e}")
        return EXIT_PROVIDER_ERROR

    sys.stdout.write(completion.text)
    if not completion.text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()

    _telemetry(
        files=len(paths),
        input_chars=len(files_block),
        output_tokens=completion.output_tokens,
        model=cfg.provider.model,
        elapsed_ms=completion.elapsed_ms,
    )
    return EXIT_OK
