"""
Rate Limiter — thread-safe implementations of three classic strategies.

Strategies
----------
1. **FixedWindow**   – allows *max_requests* per fixed time window.
2. **SlidingWindow** – sliding-log approach; accurate but higher memory.
3. **TokenBucket**   – smooth rate with burst capacity.

Each strategy exposes a simple ``acquire(key) -> bool`` interface.
A ``rate_limited`` decorator wraps any callable with automatic limiting.

All strategies are **thread-safe** (use ``threading.Lock``).
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Callable


class RateLimiterBase(ABC):
    """Common interface for all rate limiter strategies."""

    @abstractmethod
    def acquire(self, key: str = "default") -> bool:
        """Try to consume one permit. Returns True if allowed, False if limited."""

    @abstractmethod
    def reset(self, key: str | None = None) -> None:
        """Reset state for *key*, or all keys if *key* is None."""

    def __call__(self, key: str = "default") -> bool:
        return self.acquire(key)


# ---------------------------------------------------------------------------
# Fixed Window
# ---------------------------------------------------------------------------

class FixedWindowLimiter(RateLimiterBase):
    """Allows ``max_requests`` per fixed ``window_seconds`` window.

    The window resets on a wall-clock boundary (not on the first request).
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._counts: dict[str, int] = defaultdict(int)
        self._window_starts: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str = "default") -> bool:
        now = time.monotonic()
        with self._lock:
            start = self._window_starts.get(key)
            if start is None or now - start >= self.window_seconds:
                self._window_starts[key] = now
                self._counts[key] = 0
            if self._counts[key] < self.max_requests:
                self._counts[key] += 1
                return True
            return False

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._counts.clear()
                self._window_starts.clear()
            else:
                self._counts.pop(key, None)
                self._window_starts.pop(key, None)


# ---------------------------------------------------------------------------
# Sliding Window Log
# ---------------------------------------------------------------------------

class SlidingWindowLimiter(RateLimiterBase):
    """Sliding-window log: tracks every request timestamp.

    Accurate but uses O(n) memory per key where n = max_requests.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._logs: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, key: str = "default") -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            log = self._logs[key]
            # Evict expired entries from the left
            while log and log[0] <= cutoff:
                log.popleft()
            if len(log) < self.max_requests:
                log.append(now)
                return True
            return False

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._logs.clear()
            else:
                self._logs.pop(key, None)


# ---------------------------------------------------------------------------
# Token Bucket
# ---------------------------------------------------------------------------

class TokenBucketLimiter(RateLimiterBase):
    """Token-bucket algorithm with configurable refill rate and burst.

    *rate* tokens are added per second, up to a maximum of *capacity*.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        if rate < 0:
            raise ValueError("rate must be >= 0")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_time)
        self._lock = threading.Lock()

    def acquire(self, key: str = "default") -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            # Refill
            elapsed = now - last
            tokens = min(self.capacity, tokens + elapsed * self.rate)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True
            else:
                # Not enough tokens; record the current state so refill
                # continues from *now* on the next call.
                self._buckets[key] = (tokens, now)
                return False

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def rate_limited(
    limiter: RateLimiterBase,
    key: str = "default",
    *,
    raise_on_limit: bool = False,
) -> Callable:
    """Decorator that limits how often a function can be called.

    Parameters
    ----------
    limiter:
        Any :class:`RateLimiterBase` instance.
    key:
        The rate-limit key to use (default ``"default"``).
    raise_on_limit:
        If ``True``, raise ``RateLimitExceeded`` when the limit is hit.
        If ``False`` (default), return ``None`` silently.
    """

    class RateLimitExceeded(Exception):
        """Raised when the rate limit is exceeded."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if limiter.acquire(key):
                return fn(*args, **kwargs)
            if raise_on_limit:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for key={key!r} on {fn.__name__!r}"
                )
            return None

        wrapper.limiter = limiter  # type: ignore[attr-defined]
        wrapper.key = key  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import concurrent.futures

    print("=== FixedWindow (5 req / 1 sec) ===")
    fw = FixedWindowLimiter(max_requests=5, window_seconds=1.0)
    results = [fw("api") for _ in range(8)]
    print("Results:", results)  # Expect [True]*5 + [False]*3

    print("\n=== SlidingWindow (3 req / 0.5 sec) ===")
    sw = SlidingWindowLimiter(max_requests=3, window_seconds=0.5)
    for i in range(5):
        ok = sw("endpoint")
        print(f"  Request {i+1}: {'OK' if ok else 'BLOCKED'}")
        time.sleep(0.15)

    print("\n=== TokenBucket (2/sec, burst 4) ===")
    tb = TokenBucketLimiter(rate=2.0, capacity=4)
    # Drain burst
    for i in range(6):
        ok = tb()
        print(f"  Token {i+1}: {'OK' if ok else 'BLOCKED'}")

    print("\n  Waiting 1.5 sec for refill...")
    time.sleep(1.5)
    for i in range(3):
        ok = tb()
        print(f"  Token {i+1}: {'OK' if ok else 'BLOCKED'}")

    print("\n=== @rate_limited decorator ===")
    limiter = FixedWindowLimiter(max_requests=2, window_seconds=1.0)

    @rate_limited(limiter, raise_on_limit=False)
    def fetch_data(url: str) -> str:
        return f"Fetched {url}"

    for i in range(4):
        result = fetch_data("https://example.com")
        print(f"  Call {i+1}: {result!r}")

    print("\n=== Thread safety (10 threads, 100 calls, limit 20/sec) ===")
    limiter_mt = FixedWindowLimiter(max_requests=20, window_seconds=1.0)
    counter = {"allowed": 0, "blocked": 0}
    lock = threading.Lock()

    def _worker() -> None:
        for _ in range(10):
            if limiter_mt("shared"):
                with lock:
                    counter["allowed"] += 1
            else:
                with lock:
                    counter["blocked"] += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda _: _worker(), range(10)))
    print(f"  Allowed: {counter['allowed']}, Blocked: {counter['blocked']}")
    assert counter["allowed"] == 20
    assert counter["blocked"] == 80
    print("  Thread-safety check PASSED")
