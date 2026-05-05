"""Secrets-name guard for ``cheap read``.

Pure-function module. ``find_refused`` returns the list of paths whose
basenames match any glob pattern from the config. No I/O, no provider
calls — caller decides what to do with the result.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable


def find_refused(paths: Iterable[str | Path], patterns: Iterable[str]) -> list[Path]:
    """Return paths whose basename matches any glob in ``patterns``."""
    pats = tuple(patterns)
    refused: list[Path] = []
    for raw in paths:
        p = Path(raw)
        name = p.name
        if any(fnmatch.fnmatch(name, pat) for pat in pats):
            refused.append(p)
    return refused
