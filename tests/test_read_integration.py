"""Integration test against a real OpenRouter call.

Gated by env vars so normal CI skips it without network or credentials:

    RUN_INTEGRATION=1 OPENROUTER_API_KEY=sk-or-... pytest -k integration

Asserts both Phase 1 acceptance criteria from §2 of the spec:
1. Token reduction: output_tokens (from telemetry) <= 800.
2. Fidelity: every public function name from fixtures appears in the
   summary, and no fabricated names slip in.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from cheap_llm.commands import read as read_cmd

SAMPLE_DIR = Path(__file__).parent / "fixtures" / "sample_module"
INTEGRATION = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1"
    or not os.environ.get("OPENROUTER_API_KEY"),
    reason="set RUN_INTEGRATION=1 and OPENROUTER_API_KEY to run",
)

MIN_FIXTURE_TOKENS = 8_000


def _fixture_files() -> list[Path]:
    return sorted(p for p in SAMPLE_DIR.glob("*.py") if p.name != "__init__.py")


def _public_function_names(paths: list[Path]) -> set[str]:
    names: set[str] = set()
    for p in paths:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                names.add(node.name)
    return names


def _token_count(paths: list[Path]) -> int:
    """Approximate token count using tiktoken's cl100k_base."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    total = 0
    for p in paths:
        total += len(enc.encode(p.read_text(encoding="utf-8")))
    return total


@INTEGRATION
def test_fixture_set_meets_size_threshold() -> None:
    """Sanity check that the fixture is large enough for criterion §2.1."""
    files = _fixture_files()
    assert files, "fixture set must not be empty"
    tokens = _token_count(files)
    assert tokens >= MIN_FIXTURE_TOKENS, (
        f"fixture only has {tokens} tokens; spec §2.1 requires >= "
        f"{MIN_FIXTURE_TOKENS}. Add or extend fixture files."
    )


@INTEGRATION
def test_acceptance_token_reduction_and_fidelity(tmp_config, capsys) -> None:
    """Spec acceptance §2.1 + §2.2."""
    files = _fixture_files()
    rc = read_cmd.run(
        files=[str(p) for p in files],
        question="Summarise the public API and main data flow.",
        include_sensitive=False,
    )
    assert rc == read_cmd.EXIT_OK

    captured = capsys.readouterr()
    summary = captured.out
    telemetry_line = next(
        (line for line in captured.err.splitlines() if line.startswith("[cheap]")),
        "",
    )
    assert telemetry_line, "expected [cheap] telemetry line on stderr"

    # § 2.1 — Token reduction.
    m = re.search(r"output_tokens=(\d+)", telemetry_line)
    assert m, f"telemetry line missing output_tokens: {telemetry_line!r}"
    output_tokens = int(m.group(1))
    assert output_tokens <= 800, (
        f"summary too long: {output_tokens} > 800 (telemetry: {telemetry_line})"
    )

    # § 2.2 — Fidelity.
    expected_names = _public_function_names(files)
    missing = sorted(n for n in expected_names if n not in summary)
    assert not missing, f"summary omits public functions: {missing}"

    # No fabricated names — anything that LOOKS like a function call in the
    # summary should be one we actually defined. We allow stdlib/builtin
    # names by intersecting with any identifier the summary mentions
    # against the fixture's full set.
    summary_idents = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(", summary))
    suspicious = summary_idents - expected_names
    # Filter out obvious stdlib / framework references — accept names that
    # appear in the fixture sources literally (e.g. `dataclass`, `field`).
    fixture_text = "\n".join(p.read_text(encoding="utf-8") for p in files)
    fabricated = {s for s in suspicious if s not in fixture_text}
    assert not fabricated, (
        f"summary appears to invent functions not in fixtures: {sorted(fabricated)}"
    )
