"""
AsyncHTTPFetcher: Concurrent HTTP fetcher with retry, backoff, and timeout support.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of a single HTTP fetch attempt."""
    url: str
    status: int | None = None
    body: Any = None
    error: str | None = None
    elapsed: float = 0.0
    attempts: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and 200 <= self.status < 400


@dataclass
class FetcherConfig:
    """Configuration for AsyncHTTPFetcher."""
    concurrency: int = 10
    max_retries: int = 3
    base_delay: float = 0.5          # seconds; doubles each retry
    request_timeout: float = 30.0    # per-request timeout in seconds
    response_timeout: float = 60.0   # total response read timeout
    headers: dict[str, str] = field(default_factory=dict)


class AsyncHTTPFetcher:
    """Fetch many URLs concurrently with retry and exponential backoff.

    Usage::

        fetcher = AsyncHTTPFetcher(concurrency=20, max_retries=3)
        results = await fetcher.fetch_all(urls)
        for r in results:
            if r.ok:
                print(r.url, len(r.body))
            else:
                print(r.url, r.error)
    """

    def __init__(
        self,
        concurrency: int = 10,
        max_retries: int = 3,
        base_delay: float = 0.5,
        request_timeout: float = 30.0,
        response_timeout: float = 60.0,
        headers: dict[str, str] | None = None,
        config: FetcherConfig | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = FetcherConfig(
                concurrency=concurrency,
                max_retries=max_retries,
                base_delay=base_delay,
                request_timeout=request_timeout,
                response_timeout=response_timeout,
                headers=headers or {},
            )
        self._semaphore: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_all(self, urls: list[str]) -> list[FetchResult]:
        """Fetch every URL in *urls* concurrently (bounded by concurrency limit).

        Returns a list of :class:`FetchResult` in the same order as *urls*.
        """
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        timeout = aiohttp.ClientTimeout(
            total=self.config.request_timeout,
            sock_read=self.config.response_timeout,
        )
        async with aiohttp.ClientSession(
            timeout=timeout, headers=self.config.headers
        ) as session:
            tasks = [self._fetch_with_retry(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_with_retry(
        self, session: aiohttp.ClientSession, url: str
    ) -> FetchResult:
        """Fetch a single URL with retry and exponential backoff."""
        result = FetchResult(url=url)
        last_exc: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            result.attempts = attempt
            start = time.monotonic()
            try:
                async with self._semaphore:  # type: ignore[arg-type]
                    async with session.get(url) as resp:
                        body = await resp.text()
                        result.status = resp.status
                        result.body = body
                        result.elapsed = time.monotonic() - start
                        result.error = None
                        # Retry on server errors (5xx)
                        if resp.status >= 500:
                            raise aiohttp.ClientResponseError(
                                resp.request_info,
                                resp.history,
                                status=resp.status,
                                message=f"Server error {resp.status}",
                            )
                        return result
            except asyncio.TimeoutError as exc:
                last_exc = exc
                result.error = f"Timeout after {self.config.request_timeout}s"
                logger.warning("Timeout fetching %s (attempt %d/%d)", url, attempt, self.config.max_retries)
            except aiohttp.ClientResponseError as exc:
                last_exc = exc
                result.error = f"HTTP {exc.status}: {exc.message}"
                logger.warning("HTTP error %s for %s (attempt %d/%d)", exc.status, url, attempt, self.config.max_retries)
            except aiohttp.ClientError as exc:
                last_exc = exc
                result.error = f"Client error: {exc}"
                logger.warning("Client error fetching %s (attempt %d/%d): %s", url, attempt, self.config.max_retries, exc)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                result.error = f"Unexpected error: {exc}"
                logger.exception("Unexpected error fetching %s (attempt %d/%d)", url, attempt, self.config.max_retries)

            result.elapsed = time.monotonic() - start

            # Backoff before retrying (skip delay on last attempt)
            if attempt < self.config.max_retries:
                delay = self.config.base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_exc is not None and result.error is None:
            result.error = str(last_exc)
        return result


# ------------------------------------------------------------------
# Demo / CLI
# ------------------------------------------------------------------

async def _demo() -> None:
    """Quick demo fetching a handful of URLs."""
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/status/500",  # will retry then fail
        "https://nonexistent.invalid",      # DNS failure
    ]

    fetcher = AsyncHTTPFetcher(concurrency=5, max_retries=2, request_timeout=10.0)
    results = await fetcher.fetch_all(urls)

    print(f"\n{'URL':<45} {'Status':>6} {'Attempts':>8} {'Time':>7}  Error")
    print("-" * 100)
    for r in results:
        status_str = str(r.status) if r.status else "N/A"
        time_str = f"{r.elapsed:.2f}s"
        print(f"{r.url:<45} {status_str:>6} {r.attempts:>8} {time_str:>7}  {r.error or 'OK'}")


if __name__ == "__main__":
    asyncio.run(_demo())
