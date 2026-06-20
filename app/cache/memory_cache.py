import time
from typing import Any, Callable


class TTLCache:
    """
    A minimal in-memory cache with time-based expiry.

    Stores a single value per key alongside the timestamp it was set.
    On read, if the value is older than its TTL, it is treated as a
    cache miss and removed.

    This is deliberately simple — one dictionary, no external service.
    For a single-instance deployment this is sufficient. The interface
    (get, set, clear) matches what a Redis-backed cache would expose,
    so swapping this for Redis later means changing this one file,
    not the routes or services that use it.
    """

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """
        Returns the cached value for key, or None if missing or expired.
        """
        entry = self._store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """
        Stores value under key, expiring after ttl_seconds.
        """
        expires_at = time.time() + ttl_seconds
        self._store[key] = (value, expires_at)

    def clear(self) -> None:
        """Removes all cached entries. Used in tests to reset state."""
        self._store.clear()


# Single shared instance for the whole application.
# Imported as: from app.cache.memory_cache import cache
cache = TTLCache()
