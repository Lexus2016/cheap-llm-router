"""Lightweight in-process metrics collector.

A small, focused fixture module — counters, gauges, histograms, all
keyed by a label tuple. No external dependencies. Realistic enough
for the fidelity test to assert against named public functions.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterator


_LOCK = threading.RLock()
_DEFAULT_BUCKETS = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


class MetricsError(Exception):
    """Raised on misuse — incompatible label set, unknown metric, etc."""


def _label_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


@dataclass
class Counter:
    """Monotonic counter."""

    name: str
    help_text: str = ""
    _values: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))

    def inc(self, amount: float = 1.0,
            labels: dict[str, str] | None = None) -> None:
        if amount < 0:
            raise MetricsError("counter increments must be non-negative")
        with _LOCK:
            self._values[_label_key(labels)] += amount

    def value(self, labels: dict[str, str] | None = None) -> float:
        with _LOCK:
            return self._values.get(_label_key(labels), 0.0)

    def all_series(self) -> list[tuple[tuple[tuple[str, str], ...], float]]:
        with _LOCK:
            return list(self._values.items())


@dataclass
class Gauge:
    """Numeric value that can go up or down."""

    name: str
    help_text: str = ""
    _values: dict[tuple, float] = field(default_factory=dict)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        with _LOCK:
            self._values[_label_key(labels)] = value

    def inc(self, amount: float = 1.0,
            labels: dict[str, str] | None = None) -> None:
        key = _label_key(labels)
        with _LOCK:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0,
            labels: dict[str, str] | None = None) -> None:
        self.inc(amount=-amount, labels=labels)

    def value(self, labels: dict[str, str] | None = None) -> float:
        with _LOCK:
            return self._values.get(_label_key(labels), 0.0)


@dataclass
class Histogram:
    """Bucketed observation with cumulative counts."""

    name: str
    help_text: str = ""
    buckets: tuple[float, ...] = _DEFAULT_BUCKETS
    _series: dict[tuple, dict[str, float]] = field(default_factory=dict)

    def _empty_series(self) -> dict[str, float]:
        body: dict[str, float] = {f"le_{b}": 0.0 for b in self.buckets}
        body["le_inf"] = 0.0
        body["sum"] = 0.0
        body["count"] = 0.0
        return body

    def observe(self, value: float,
                labels: dict[str, str] | None = None) -> None:
        key = _label_key(labels)
        with _LOCK:
            series = self._series.setdefault(key, self._empty_series())
            for b in self.buckets:
                if value <= b:
                    series[f"le_{b}"] += 1
            series["le_inf"] += 1
            series["sum"] += value
            series["count"] += 1

    def snapshot(self, labels: dict[str, str] | None = None) -> dict[str, float]:
        with _LOCK:
            return dict(self._series.get(_label_key(labels), self._empty_series()))


class Registry:
    """Holds named metrics and emits a flat snapshot for export."""

    def __init__(self) -> None:
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}

    def register(self, metric: Counter | Gauge | Histogram) -> None:
        with _LOCK:
            if metric.name in self._metrics:
                raise MetricsError(f"duplicate metric name: {metric.name!r}")
            self._metrics[metric.name] = metric

    def get(self, name: str) -> Counter | Gauge | Histogram:
        with _LOCK:
            try:
                return self._metrics[name]
            except KeyError as exc:
                raise MetricsError(f"unknown metric: {name!r}") from exc

    def all_metrics(self) -> Iterator[Counter | Gauge | Histogram]:
        with _LOCK:
            return iter(list(self._metrics.values()))


def time_block(histogram: Histogram, labels: dict[str, str] | None = None):
    """Context manager that observes the duration of a code block."""

    class _Timer:
        def __enter__(self_inner):
            self_inner.t0 = time.monotonic()
            return self_inner

        def __exit__(self_inner, *exc):
            histogram.observe(time.monotonic() - self_inner.t0, labels=labels)
            return False

    return _Timer()
