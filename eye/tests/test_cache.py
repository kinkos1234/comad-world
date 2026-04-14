"""Tests for utils/cache.py — TTL LRU cache."""

from __future__ import annotations

import threading
import time

import pytest

from comad_eye.cache import TTLCache, _SENTINEL


# ---------------------------------------------------------------------------
# Basic get / set
# ---------------------------------------------------------------------------

class TestBasicGetSet:
    def test_set_and_get_returns_value(self):
        cache = TTLCache(ttl=60)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_get_missing_key_returns_none(self):
        cache = TTLCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_set_none_value_is_distinguishable_via_sentinel(self):
        cache = TTLCache(ttl=60)
        cache.set("k", None)
        result = cache.get_or_sentinel("k")
        assert result is not _SENTINEL
        assert result is None

    def test_overwrite_key(self):
        cache = TTLCache(ttl=60)
        cache.set("k", 1)
        cache.set("k", 2)
        assert cache.get("k") == 2

    def test_multiple_keys(self):
        cache = TTLCache(ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_stores_various_value_types(self):
        cache = TTLCache(ttl=60)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"x": 1})
        cache.set("int", 42)
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"x": 1}
        assert cache.get("int") == 42


# ---------------------------------------------------------------------------
# TTL expiration
# ---------------------------------------------------------------------------

class TestTTLExpiration:
    def test_entry_expires_after_ttl(self):
        cache = TTLCache(ttl=0.05)  # 50 ms
        cache.set("k", "v")
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_entry_alive_before_ttl(self):
        cache = TTLCache(ttl=5)
        cache.set("k", "v")
        time.sleep(0.01)
        assert cache.get("k") == "v"

    def test_expired_key_returns_sentinel(self):
        cache = TTLCache(ttl=0.05)
        cache.set("k", "v")
        time.sleep(0.1)
        assert cache.get_or_sentinel("k") is _SENTINEL

    def test_per_entry_ttl_override(self):
        cache = TTLCache(ttl=60)
        cache.set("short", "v", ttl=0.05)
        time.sleep(0.1)
        assert cache.get("short") is None

    def test_per_entry_ttl_longer_than_default(self):
        cache = TTLCache(ttl=0.05)
        cache.set("long", "v", ttl=60)
        time.sleep(0.1)
        assert cache.get("long") == "v"

    def test_size_decreases_after_expiry_check(self):
        cache = TTLCache(ttl=0.05)
        cache.set("k", "v")
        time.sleep(0.1)
        assert cache.size() == 0

    def test_expired_entry_removed_on_get(self):
        cache = TTLCache(ttl=0.05, max_size=1)
        cache.set("k", "v")
        time.sleep(0.1)
        cache.get("k")  # triggers removal
        assert len(cache) == 0  # internal store cleaned up

    def test_mock_time_via_monkeypatch(self, monkeypatch):
        """Verify expiry logic using monkeypatched time.monotonic."""
        import comad_eye.cache as cache_mod

        now = [0.0]

        def fake_monotonic():
            return now[0]

        monkeypatch.setattr(cache_mod.time, "monotonic", fake_monotonic)

        cache = TTLCache(ttl=10)
        cache.set("k", "v")
        assert cache.get("k") == "v"

        now[0] = 11.0  # advance past TTL
        assert cache.get("k") is None


# ---------------------------------------------------------------------------
# max_size eviction (LRU)
# ---------------------------------------------------------------------------

class TestMaxSizeEviction:
    def test_lru_eviction_when_full(self):
        cache = TTLCache(ttl=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 'a' should be evicted (LRU)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_access_refreshes_lru_order(self):
        cache = TTLCache(ttl=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access 'a' to make it recently used
        cache.get("a")
        # Now 'b' should be the LRU candidate
        cache.set("d", 4)
        assert cache.get("a") == 1
        assert cache.get("b") is None  # evicted
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_overwrite_does_not_grow_beyond_max(self):
        cache = TTLCache(ttl=60, max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("a", 99)  # overwrite, not a new entry
        assert len(cache) == 2

    def test_max_size_one(self):
        cache = TTLCache(ttl=60, max_size=1)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_constructor_rejects_zero_max_size(self):
        with pytest.raises(ValueError):
            TTLCache(ttl=60, max_size=0)

    def test_constructor_rejects_zero_ttl(self):
        with pytest.raises(ValueError):
            TTLCache(ttl=0)

    def test_constructor_rejects_negative_ttl(self):
        with pytest.raises(ValueError):
            TTLCache(ttl=-1)


# ---------------------------------------------------------------------------
# Invalidation & clear
# ---------------------------------------------------------------------------

class TestInvalidation:
    def test_invalidate_removes_key(self):
        cache = TTLCache(ttl=60)
        cache.set("k", "v")
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_missing_key_is_noop(self):
        cache = TTLCache(ttl=60)
        cache.invalidate("nonexistent")  # should not raise

    def test_clear_removes_all_entries(self):
        cache = TTLCache(ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert len(cache) == 0

    def test_set_after_invalidate_works(self):
        cache = TTLCache(ttl=60)
        cache.set("k", "old")
        cache.invalidate("k")
        cache.set("k", "new")
        assert cache.get("k") == "new"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_writes_no_data_loss(self):
        cache = TTLCache(ttl=60, max_size=1000)
        errors: list[Exception] = []

        def writer(start: int) -> None:
            try:
                for i in range(start, start + 100):
                    cache.set(str(i), i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in threads: {errors}"

    def test_concurrent_reads_and_writes(self):
        cache = TTLCache(ttl=60, max_size=50)
        errors: list[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for i in range(50):
                    key = str(i % 10)
                    if i % 2 == 0:
                        cache.set(key, thread_id * 100 + i)
                    else:
                        cache.get(key)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in threads: {errors}"

    def test_concurrent_clear_and_set(self):
        cache = TTLCache(ttl=60, max_size=100)
        errors: list[Exception] = []

        def setter() -> None:
            try:
                for i in range(200):
                    cache.set(str(i), i)
            except Exception as exc:
                errors.append(exc)

        def clearer() -> None:
            try:
                for _ in range(20):
                    cache.clear()
                    time.sleep(0.001)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=setter),
            threading.Thread(target=clearer),
            threading.Thread(target=setter),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in threads: {errors}"

    def test_concurrent_invalidation(self):
        cache = TTLCache(ttl=60, max_size=100)
        errors: list[Exception] = []
        # Pre-populate
        for i in range(50):
            cache.set(str(i), i)

        def invalidator(start: int) -> None:
            try:
                for i in range(start, start + 25):
                    cache.invalidate(str(i))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=invalidator, args=(0,)),
            threading.Thread(target=invalidator, args=(25,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in threads: {errors}"


# ---------------------------------------------------------------------------
# Module-level singletons sanity check
# ---------------------------------------------------------------------------

class TestModuleSingletons:
    def test_singletons_exist_with_correct_ttl(self):
        from comad_eye.cache import (
            analysis_file_cache,
            graph_counts_cache,
            graph_stats_cache,
        )
        assert graph_stats_cache.ttl == 60
        assert graph_counts_cache.ttl == 30
        assert analysis_file_cache.ttl == 120

    def test_singletons_are_usable(self):
        from comad_eye.cache import graph_stats_cache

        graph_stats_cache.set("test_key", {"nodes": 42})
        assert graph_stats_cache.get("test_key") == {"nodes": 42}
        graph_stats_cache.invalidate("test_key")
        assert graph_stats_cache.get("test_key") is None
