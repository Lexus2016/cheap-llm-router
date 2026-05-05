"""In-memory toy data store with a transaction abstraction.

Used as a fidelity-test fixture: stable, named functions and types
that the summary should mention by name without inventing extras.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


_LOCK = threading.RLock()
_DEFAULT_PAGE_SIZE = 50


class StoreError(Exception):
    """Raised on any store-level failure (missing key, bad type, etc.)."""


@dataclass
class Record:
    """One row in a logical table."""

    key: str
    value: dict[str, Any]
    version: int = 1
    deleted: bool = False


@dataclass
class Table:
    """A simple keyed collection of Record objects."""

    name: str
    rows: dict[str, Record] = field(default_factory=dict)

    def upsert(self, key: str, value: dict[str, Any]) -> Record:
        with _LOCK:
            existing = self.rows.get(key)
            if existing is None:
                rec = Record(key=key, value=dict(value))
            else:
                rec = Record(key=key, value=dict(value), version=existing.version + 1)
            self.rows[key] = rec
            return rec

    def get(self, key: str) -> Record:
        with _LOCK:
            rec = self.rows.get(key)
            if rec is None or rec.deleted:
                raise StoreError(f"no record for key={key!r}")
            return rec

    def soft_delete(self, key: str) -> None:
        with _LOCK:
            rec = self.rows.get(key)
            if rec is None:
                raise StoreError(f"cannot delete missing key={key!r}")
            rec.deleted = True


@dataclass
class Store:
    """Top-level container for several tables."""

    tables: dict[str, Table] = field(default_factory=dict)

    def table(self, name: str) -> Table:
        with _LOCK:
            if name not in self.tables:
                self.tables[name] = Table(name=name)
            return self.tables[name]

    def drop(self, name: str) -> None:
        with _LOCK:
            self.tables.pop(name, None)

    def snapshot(self) -> str:
        """Serialise the entire store to JSON for backup or testing."""
        with _LOCK:
            payload = {
                name: {
                    key: {
                        "value": rec.value,
                        "version": rec.version,
                        "deleted": rec.deleted,
                    }
                    for key, rec in tbl.rows.items()
                }
                for name, tbl in self.tables.items()
            }
            return json.dumps(payload, sort_keys=True, indent=2)


@contextmanager
def transaction(store: Store) -> Iterator[Store]:
    """Best-effort transaction: snapshot before, restore on error.

    Toy semantics — does not handle nested transactions or partial
    rollback of mutated nested values; intended for the fixture's
    illustrative scope only.
    """
    backup = store.snapshot()
    try:
        yield store
    except Exception:
        restored = json.loads(backup)
        with _LOCK:
            store.tables.clear()
            for name, rows in restored.items():
                tbl = Table(name=name)
                for key, payload in rows.items():
                    tbl.rows[key] = Record(
                        key=key,
                        value=payload["value"],
                        version=payload["version"],
                        deleted=payload["deleted"],
                    )
                store.tables[name] = tbl
        raise


def page_records(table: Table, page: int = 0,
                 page_size: int = _DEFAULT_PAGE_SIZE) -> list[Record]:
    """Return a page of non-deleted records in insertion order."""
    if page < 0 or page_size <= 0:
        raise StoreError("page must be >= 0 and page_size > 0")
    keys = [k for k, r in table.rows.items() if not r.deleted]
    start, end = page * page_size, (page + 1) * page_size
    return [table.rows[k] for k in keys[start:end]]


def count_active(table: Table) -> int:
    """Number of non-deleted rows in a table."""
    return sum(1 for r in table.rows.values() if not r.deleted)


def find_by_value(table: Table, key: str, expected: Any) -> list[Record]:
    """Linear search returning rows whose ``value[key] == expected``."""
    out: list[Record] = []
    for rec in table.rows.values():
        if rec.deleted:
            continue
        if rec.value.get(key) == expected:
            out.append(rec)
    return out


def restore_snapshot(store: Store, snapshot: str) -> None:
    """Replace the store's contents with a previously taken snapshot."""
    payload = json.loads(snapshot)
    with _LOCK:
        store.tables.clear()
        for name, rows in payload.items():
            tbl = Table(name=name)
            for key, body in rows.items():
                tbl.rows[key] = Record(
                    key=key,
                    value=body["value"],
                    version=body["version"],
                    deleted=body["deleted"],
                )
            store.tables[name] = tbl
