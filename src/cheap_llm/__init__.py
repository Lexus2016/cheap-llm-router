"""cheap-llm-router — delegate read-for-context summaries to a cheap LLM."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__: str = _pkg_version("cheap-llm-router")
except PackageNotFoundError:
    # Bare-source run (no dist-info installed). Tests and `python -m cheap_llm`
    # from a fresh clone hit this path.
    __version__ = "0.0.0+local"

# Bumped 2 → 3 alongside CLAUDE.md v9.0 alignment (slimmed template body,
# v9-native skip behavior in install_rule).
RULE_TEMPLATE_VERSION: int = 3

__all__ = ["__version__", "RULE_TEMPLATE_VERSION"]
