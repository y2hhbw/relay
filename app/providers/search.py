from typing import Any

import httpx


class SearchProviderError(Exception):
    pass


def _mock_search(query: str) -> dict[str, Any]:
    if query == "fail":
        raise SearchProviderError

    return {
        "results": [
            {
                "title": f"Search result for {query}",
                "url": "https://example.com/result",
            }
        ]
    }


def _duckduckgo_search(query: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise SearchProviderError from exc

    title = payload.get("Heading") or f"Search result for {query}"
    abstract_url = payload.get("AbstractURL") or "https://duckduckgo.com"
    abstract = payload.get("Abstract") or ""
    return {
        "results": [
            {
                "title": title,
                "url": abstract_url,
                "snippet": abstract,
            }
        ]
    }


def search_web(query: str, *, provider_mode: str, timeout_seconds: float) -> dict[str, Any]:
    if provider_mode == "duckduckgo":
        return _duckduckgo_search(query, timeout_seconds)
    return _mock_search(query)
