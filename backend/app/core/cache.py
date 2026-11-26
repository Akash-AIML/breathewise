"""Small bounded-cache helpers used by provider adapters and services.

These are deliberately simple FIFO/TTL caches: correctness depends on freshness
checks at read time, and the cap prevents attacker-controlled keys from growing
memory without limit.
"""

from collections.abc import Callable, MutableMapping
from datetime import UTC, datetime
from typing import Any


def prune_expired(
    mapping: MutableMapping[Any, Any],
    expires_at: Callable[[Any], datetime],
    now: datetime | None = None,
) -> None:
    """Remove entries whose expiry has passed."""
    current = now or datetime.now(UTC)
    for key, value in list(mapping.items()):
        if expires_at(value) <= current:
            mapping.pop(key, None)


def enforce_limit(mapping: MutableMapping[Any, Any], max_entries: int) -> None:
    """Evict the oldest inserted keys until the mapping is within its cap."""
    while len(mapping) > max(0, max_entries):
        mapping.pop(next(iter(mapping)))


def bound_locks(locks: MutableMapping[Any, Any], max_locks: int) -> None:
    """Remove idle per-key locks; never evict one that is in use."""
    for key in list(locks):
        if len(locks) <= max(0, max_locks):
            break
        lock = locks[key]
        if not lock.locked():
            locks.pop(key, None)
