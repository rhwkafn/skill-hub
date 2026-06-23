"""
Caching Decorator with LRU eviction and hit/miss statistics.

Provides a @cache(max_size=N) decorator that caches function results
based on arguments, evicts least-recently-used entries when full,
and tracks cache hit/miss statistics.
"""

import functools
import threading
from collections import OrderedDict
from typing import Any, Callable


def cache(max_size: int = 128) -> Callable:
    """
    Decorator that caches function results based on arguments.

    Args:
        max_size: Maximum number of cached results (LRU eviction when exceeded).
                  Must be a positive integer.

    Returns:
        A decorator that wraps the function with caching logic.

    The decorated function exposes:
        - cache_info() -> dict with hits, misses, size, max_size
        - cache_clear() -> clears the cache and resets stats
    """
    if max_size < 1:
        raise ValueError("max_size must be at least 1")

    def decorator(func: Callable) -> Callable:
        # Use OrderedDict for O(1) LRU: move_to_end on access, popitem(last=False) for eviction
        _cache: OrderedDict[Any, Any] = OrderedDict()
        _hits = 0
        _misses = 0
        _lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal _hits, _misses

            # Build a hashable key from positional and keyword args
            key = _make_key(args, kwargs)

            with _lock:
                if key in _cache:
                    # Cache hit - move to end (most recently used)
                    _cache.move_to_end(key)
                    _hits += 1
                    return _cache[key]

            # Cache miss - compute outside lock to avoid holding it during function execution
            result = func(*args, **kwargs)

            with _lock:
                _misses += 1
                _cache[key] = result

                # LRU eviction if over capacity
                while len(_cache) > max_size:
                    _cache.popitem(last=False)  # Remove least recently used

            return result

        def cache_info() -> dict:
            """Return cache statistics."""
            with _lock:
                return {
                    "hits": _hits,
                    "misses": _misses,
                    "size": len(_cache),
                    "max_size": max_size,
                }

        def cache_clear() -> None:
            """Clear the cache and reset statistics."""
            nonlocal _hits, _misses
            with _lock:
                _cache.clear()
                _hits = 0
                _misses = 0

        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        wrapper._cache = _cache  # type: ignore[attr-defined]  # For testing/inspection

        return wrapper  # type: ignore[return-value]

    return decorator


def _make_key(args: tuple, kwargs: dict) -> tuple:
    """
    Build a hashable cache key from positional and keyword arguments.

    Handles nested dicts/lists by converting them to frozen representations.
    """
    key_parts: list[Any] = [_freeze(a) for a in args]
    if kwargs:
        # Sort kwargs for consistent key generation
        key_parts.append(tuple(sorted(
            (k, _freeze(v)) for k, v in kwargs.items()
        )))
    return tuple(key_parts)


def _freeze(obj: Any) -> Any:
    """Convert a value to a hashable representation for use as a cache key."""
    if isinstance(obj, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(item) for item in obj)
    if isinstance(obj, set):
        return frozenset(_freeze(item) for item in obj)
    return obj


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    @cache(max_size=3)
    def add(a, b):
        print(f"  Computing add({a}, {b})")
        return a + b

    @cache(max_size=2)
    def greet(name="World"):
        print(f"  Computing greet({name!r})")
        return f"Hello, {name}!"

    print("=== add() tests ===")
    print(f"add(1, 2) = {add(1, 2)}")
    print(f"add(1, 2) = {add(1, 2)}")  # hit
    print(f"add(3, 4) = {add(3, 4)}")
    print(f"add(5, 6) = {add(5, 6)}")
    print(f"add(7, 8) = {add(7, 8)}")  # should evict (1,2) since max_size=3
    print(f"add(1, 2) = {add(1, 2)}")  # miss - was evicted
    print(f"Stats: {add.cache_info()}")

    print("\n=== greet() tests ===")
    print(f"greet() = {greet()}")
    print(f"greet() = {greet()}")  # hit
    print(f"greet('Alice') = {greet('Alice')}")
    print(f"greet() = {greet()}")  # hit
    print(f"Stats: {greet.cache_info()}")

    print("\n=== clear test ===")
    add.cache_clear()
    print(f"After clear: {add.cache_info()}")
