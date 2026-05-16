from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .registry import ToolRegistry

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_FETCH_MAX_CHARS = 8000


def _unwrap_ddg_url(href: str) -> str:
    """DuckDuckGo wraps result URLs in a redirect. Unwrap to the real URL."""
    if not href:
        return href
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    return href


def register(registry: ToolRegistry) -> None:

    # ------------------------------------------------------------------ #
    # web_search
    # ------------------------------------------------------------------ #
    async def web_search(query: str, max_results: int = 5) -> str:
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS, timeout=15, follow_redirects=True
            ) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/", params={"q": query}
                )
                resp.raise_for_status()
        except Exception as e:
            return f"Search error: {e}"

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[str] = []

        for r in soup.select(".result")[:max_results]:
            title_el = r.select_one(".result__a")
            snippet_el = r.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = _unwrap_ddg_url(title_el.get("href", ""))
            results.append(f"Title:   {title}\nSnippet: {snippet}\nURL:     {url}")

        if not results:
            return f"No results found for '{query}'."
        header = f"Top {len(results)} results for '{query}':\n"
        return header + "\n\n".join(f"{i+1}. {r}" for i, r in enumerate(results))

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the web via DuckDuckGo. "
                    "Returns titles, snippets, and URLs for the top results."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 5).",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        web_search,
    )

    # ------------------------------------------------------------------ #
    # web_fetch
    # ------------------------------------------------------------------ #
    async def web_fetch(url: str) -> str:
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS, timeout=20, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except Exception as e:
            return f"Fetch error: {e}"

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip non-content elements
        for tag in soup(
            ["script", "style", "nav", "footer", "header",
             "aside", "form", "iframe", "noscript"]
        ):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        condensed = "\n".join(lines)

        if len(condensed) > _FETCH_MAX_CHARS:
            condensed = (
                condensed[:_FETCH_MAX_CHARS]
                + f"\n\n[truncated — {len(condensed)} total chars]"
            )

        return condensed or "(no readable text content found)"

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "web_fetch",
                "description": (
                    "Fetch a web page and return its readable text content. "
                    "Scripts, navigation, and boilerplate are stripped. "
                    "Output is truncated at 8000 chars."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Full URL to fetch.",
                        }
                    },
                    "required": ["url"],
                },
            },
        },
        web_fetch,
    )
