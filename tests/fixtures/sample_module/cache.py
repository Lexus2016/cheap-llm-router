"""Toy LRU + TTL cache used by handlers and db.

A fourth fixture file so the sample module's source size clears the
acceptance-criterion threshold (≥ 8 000 tokens). Realistic enough
shape that summaries can be evaluated for fidelity.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Hashable, Iterator, Optional, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

DEFAULT_MAX_ENTRIES = 512
DEFAULT_TTL_SECONDS = 5 * 60


class CacheError(Exception):
    """Raised on misuse — unknown key when ``get`` is strict, etc."""


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0


@dataclass
class _Entry(Generic[V]):
    value: V
    inserted_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class LruTtlCache(Generic[K, V]):
    """Thread-safe LRU cache with per-entry TTL."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES,
                 default_ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        if max_entries <= 0:
            raise CacheError("max_entries must be > 0")
        if default_ttl_seconds <= 0:
            raise CacheError("default_ttl_seconds must be > 0")
        self._max_entries = max_entries
        self._default_ttl = default_ttl_seconds
        self._lock = threading.RLock()
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self.stats = CacheStats()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, key: K) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._evict(key, expired=True)
                return False
            return True

    def __iter__(self) -> Iterator[K]:
        with self._lock:
            return iter(list(self._entries.keys()))

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Return the cached value or ``default``. Updates LRU order."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.stats.misses += 1
                return default
            if entry.is_expired:
                self._evict(key, expired=True)
                self.stats.misses += 1
                return default
            self._entries.move_to_end(key)
            self.stats.hits += 1
            return entry.value

    def get_strict(self, key: K) -> V:
        """Like ``get`` but raises ``CacheError`` if not present."""
        sentinel = object()
        value = self.get(key, default=sentinel)  # type: ignore[arg-type]
        if value is sentinel:
            raise CacheError(f"no cache entry for key={key!r}")
        return value  # type: ignore[return-value]

    def put(self, key: K, value: V,
            ttl_seconds: Optional[int] = None) -> None:
        """Insert or replace an entry; evict LRU if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        if ttl <= 0:
            raise CacheError("ttl_seconds must be > 0")
        now = time.time()
        with self._lock:
            self._entries[key] = _Entry(
                value=value, inserted_at=now, expires_at=now + ttl
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                evicted, _ = self._entries.popitem(last=False)
                self.stats.evictions += 1
                _ = evicted  # for clarity / hooks

    def pop(self, key: K) -> Optional[V]:
        """Remove and return ``value`` for ``key`` if present."""
        with self._lock:
            entry = self._entries.pop(key, None)
            return entry.value if entry is not None else None

    def clear(self) -> None:
        """Drop all entries; does not reset stats."""
        with self._lock:
            self._entries.clear()

    def items_snapshot(self) -> list[tuple[K, V]]:
        """Return a stable list of (key, value) pairs for inspection."""
        with self._lock:
            return [(k, e.value) for k, e in self._entries.items()
                    if not e.is_expired]

    def reap_expired(self) -> int:
        """Drop all entries that have passed their expiry. Returns the count."""
        with self._lock:
            keys = [k for k, e in self._entries.items() if e.is_expired]
            for k in keys:
                self._evict(k, expired=True)
            return len(keys)

    def _evict(self, key: K, *, expired: bool) -> None:
        # Caller must hold ``self._lock``.
        self._entries.pop(key, None)
        if expired:
            self.stats.expirations += 1
        else:
            self.stats.evictions += 1


def memoize(cache: LruTtlCache, key_fn: Callable[..., Hashable] | None = None,
            ttl_seconds: Optional[int] = None) -> Callable:
    """Decorator caching the wrapped function's return value.

    Example::

        cache = LruTtlCache()
        @memoize(cache)
        def slow_lookup(user_id: str) -> dict: ...
    """

    def decorator(fn: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_fn(*args, **kwargs) if key_fn else (fn.__name__, args,
                                                          tuple(sorted(kwargs.items())))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = fn(*args, **kwargs)
            cache.put(key, result, ttl_seconds=ttl_seconds)
            return result

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator


def warm_cache(cache: LruTtlCache, source: dict[Any, Any],
               ttl_seconds: Optional[int] = None) -> int:
    """Pre-load ``cache`` from a plain dict. Returns count inserted."""
    count = 0
    for key, value in source.items():
        cache.put(key, value, ttl_seconds=ttl_seconds)
        count += 1
    return count
