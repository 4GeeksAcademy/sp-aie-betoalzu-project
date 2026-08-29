"""In-memory TTL cache for backend endpoints.

Provides a simple dict-based cache with time-to-live (TTL) expiration
and manual invalidation by tag groups.
"""

from __future__ import annotations

import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable


class TTLCache:
    """Thread-safe (for single-threaded ASGI) in-memory cache with TTL support.

    Each entry stores:
      - value: the cached result
      - expiry: absolute timestamp after which the entry is stale
      - tags: set of tag strings for grouped invalidation

    Usage:
        cache = TTLCache(default_ttl=300)  # 5 minutes

        @cache.cached(ttl=120)
        def expensive_func(arg):
            ...

        cache.invalidate_tag("incidents")  # clears all entries tagged "incidents"
        cache.clear()                      # clears entire cache
    """

    def __init__(self, default_ttl: int = 300) -> None:
        self._default_ttl = default_ttl
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}
        self._tags: dict[str, set[str]] = defaultdict(set)

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Build a cache key from function identity and arguments."""
        parts = [func_name]
        parts.extend(str(a) for a in args)
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return "::".join(parts)

    def get(self, key: str) -> Any | None:
        """Return the cached value if it exists and is fresh, else None."""
        if key not in self._store:
            return None
        if time.time() > self._expiry.get(key, 0):
            # Expired — remove
            del self._store[key]
            self._expiry.pop(key, None)
            self._tags[key].discard(key)
            return None
        return self._store[key]

    def set(self, key: str, value: Any, ttl: int | None = None, tags: list[str] | None = None) -> None:
        """Store a value in the cache with optional TTL (in seconds) and tags."""
        self._store[key] = value
        self._expiry[key] = time.time() + (ttl if ttl is not None else self._default_ttl)
        if tags:
            for tag in tags:
                self._tags[tag].add(key)

    def invalidate_tag(self, tag: str) -> int:
        """Remove all cache entries associated with *tag*. Returns count removed."""
        keys_to_remove = list(self._tags.get(tag, set()))
        for key in keys_to_remove:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
        self._tags[tag] = set()
        return len(keys_to_remove)

    def invalidate_tags(self, tags: list[str]) -> int:
        """Remove all cache entries associated with any of the given tags."""
        total = 0
        for tag in tags:
            total += self.invalidate_tag(tag)
        return total

    def clear(self) -> None:
        """Clear the entire cache."""
        self._store.clear()
        self._expiry.clear()
        self._tags.clear()

    def cached(self, ttl: int | None = None, tags: list[str] | None = None) -> Callable:
        """Decorator: cache the return value of a function.

        The cache key is derived from the function name + arguments.
        If *ttl* is omitted, the instance's default_ttl is used.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = self._make_key(func.__name__, args, kwargs)
                cached = self.get(key)
                if cached is not None:
                    return cached
                result = func(*args, **kwargs)
                self.set(key, result, ttl=ttl, tags=tags)
                return result
            return wrapper
        return decorator


# ---------------------------------------------------------------------------
# Global cache instance – shared across all endpoint modules
# ---------------------------------------------------------------------------
backend_cache = TTLCache(default_ttl=120)  # 2 minutes default