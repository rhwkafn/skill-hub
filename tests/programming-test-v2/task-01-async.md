# Task 1: Async HTTP Fetcher

Write an async Python function that:
- Fetches multiple URLs concurrently using asyncio + aiohttp
- Returns dict of {url: response_text}
- Handles timeouts and errors gracefully
- Includes retry logic (max 3 retries)

Save to: `tests/programming-test-v2/solutions/async_fetcher.py`
