"""Simple in-memory TTL LRU cache for ComadEye.

Provides a thread-safe cache with configurable TTL and max size.
No external dependencies — pure stdlib.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any


_SENTINEL = object()  # signals a cache miss distinct from a stored None value


class TTLCache:
    """Thread-safe in-memory LRU cache with per-entry TTL.

    Args:
        ttl: Time-to-live in seconds for each cached entry (default 300).
        max_size: Maximum number of entries before LRU eviction (default 256).
    """

    def __init__(self, ttl: float = 300, max_size: int = 256) -> None:
        if ttl <= 0:
            raise ValueError(f"ttl must be positive, got {ttl}")
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")

        self._ttl = ttl
        self._max_size = max_size
        # OrderedDict preserves insertion/access order for LRU tracking.
        # Each value is (stored_value, expiry_timestamp).
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any:
        """Return the cached value for *key*, or ``None`` on a miss/expiry.

        To distinguish a stored ``None`` from a cache miss, use
        :py:meth:`get_or_sentinel` instead.
        """
        value = self.get_or_sentinel(key)
        return None if value is _SENTINEL else value

    def get_or_sentinel(self, key: str) -> Any:
        """Return the cached value, or the module-level ``_SENTINEL`` on miss."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return _SENTINEL
            value, expiry = entry
            if time.monotonic() >= expiry:
                # Expired — remove and treat as miss.
                del self._store[key]
                return _SENTINEL
            # Move to end (most-recently-used).
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key* with an optional per-entry *ttl* override."""
        effective_ttl = ttl if ttl is not None else self._ttl
        expiry = time.monotonic() + effective_ttl
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expiry)
            # Evict LRU entries if we exceed max_size.
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Remove *key* from the cache (no-op if absent)."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()

    # ------------------------------------------------------------------
    # Introspection helpers (useful for tests and health checks)
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of entries currently in the cache (including expired)."""
        with self._lock:
            return len(self._store)

    @property
    def ttl(self) -> float:
        return self._ttl

    @property
    def max_size(self) -> int:
        return self._max_size

    def size(self) -> int:
        """Return the number of *live* (non-expired) entries."""
        now = time.monotonic()
        with self._lock:
            return sum(1 for _, expiry in self._store.values() if now < expiry)


# ---------------------------------------------------------------------------
# Module-level singleton caches (one per domain area).
# Using separate instances keeps TTL semantics independent.
# ---------------------------------------------------------------------------

#: Cache for Neo4j graph stats (get_graph_stats). TTL 60 s.
graph_stats_cache: TTLCache = TTLCache(ttl=60, max_size=32)

#: Cache for cheap count queries (node_count / edge_count). TTL 30 s.
graph_counts_cache: TTLCache = TTLCache(ttl=30, max_size=32)

#: Cache for analysis JSON file reads. TTL 120 s.
analysis_file_cache: TTLCache = TTLCache(ttl=120, max_size=256)
