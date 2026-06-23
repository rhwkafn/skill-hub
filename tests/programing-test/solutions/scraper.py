"""
Simple web scraper using only requests + re (no BeautifulSoup).
Fetches a webpage, extracts links and title, returns a structured dict.
"""

import re
from typing import Optional


def scrape_page(url: str, timeout: int = 10) -> dict:
    """
    Fetch a webpage and extract links and title.

    Args:
        url: The URL to scrape.
        timeout: Request timeout in seconds.

    Returns:
        dict with keys:
            - url (str): the original URL
            - title (str | None): page title, or None if not found
            - links (list[dict]): list of {href, text} dicts for each <a> tag
            - error (str | None): error message if the request failed
    """
    import requests

    result: dict = {
        "url": url,
        "title": None,
        "links": [],
        "error": None,
    }

    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "SimpleScraper/1.0"
        })
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    # Extract page title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        result["title"] = title_match.group(1).strip()

    # Extract all <a ... href="..." ...>...</a> links
    # Step 1: find all anchor tags with their content
    anchor_pattern = re.compile(
        r'<a\s[^>]*?href\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in anchor_pattern.finditer(html):
        href = match.group(1).strip()
        # Strip HTML tags from the link text
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        result["links"].append({"href": href, "text": text})

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    data = scrape_page(target)
    print(json.dumps(data, indent=2, ensure_ascii=False))
