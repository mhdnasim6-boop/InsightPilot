"""Web search for the Research Agent (Tavily news search), returning structured, citable results."""
from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlparse

from langchain_core.tools import tool

from ..config import Settings


class SearchUnavailable(RuntimeError):
    """Web search is not configured (no API key) or failed."""


def publisher_of(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def normalise_results(raw_results: list[dict]) -> list[dict]:
    """Keep only what the report needs; the URL and published date are preserved exactly."""
    out = []
    for r in raw_results or []:
        url = r.get("url")
        if not url:
            continue
        out.append({
            "title": (r.get("title") or "").strip(),
            "url": url,
            "publisher": publisher_of(url),
            "published_date": r.get("published_date") or r.get("published_time") or None,
            "snippet": (r.get("content") or r.get("snippet") or "").strip()[:500],
        })
    return out


def tavily_search(query: str, settings: Settings) -> list[dict]:
    if not settings.tavily_api_key:
        raise SearchUnavailable("TAVILY_API_KEY is not set")
    from langchain_tavily import TavilySearch
    from pydantic import SecretStr

    tool_ = TavilySearch(max_results=5, topic="news", tavily_api_key=SecretStr(settings.tavily_api_key))
    raw = tool_.invoke({"query": query})
    if not isinstance(raw, dict):
        raise SearchUnavailable(str(raw)[:200])
    return normalise_results(raw.get("results", []))


def make_search_tool(settings: Settings, search_fn: Callable[[str], list[dict]] | None = None):
    """Build the `web_search` tool. `search_fn` can be injected (tests); default is Tavily."""
    fn = search_fn or (lambda q: tavily_search(q, settings))

    @tool
    def web_search(query: str) -> str:
        """Search recent news and web pages for context about a business trend.
        Returns JSON: a list of results, each with title, url, publisher, published_date and snippet.
        Use specific queries that name the industry, region and time period."""
        last_err = ""
        for _ in range(2):  # one retry on failure
            try:
                results = fn(query)
                return json.dumps({"ok": True, "query": query, "results": results})
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)[:200]
        return json.dumps({"ok": False, "query": query, "error": last_err, "results": []})

    return web_search
