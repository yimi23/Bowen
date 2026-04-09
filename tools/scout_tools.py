"""
tools/scout_tools.py — SCOUT tool implementations.
Phase 5+: Brave Search replaces Tavily (1,000 free/month vs 200).
web_search (Brave), web_fetch, document_parse, structured_extract.
"""

import json
from typing import Any

import requests
from bs4 import BeautifulSoup


# ── Anthropic tool schemas ────────────────────────────────────────────────────

SCOUT_TOOL_SCHEMAS = [
    {
        "name": "web_search",
        "description": (
            "Search the web using Brave Search API. Returns structured results with titles, URLs, and descriptions. "
            "Use for: research, competitive analysis, finding facts, current events, technical docs. "
            "Better than raw search — results are clean and structured for LLM consumption."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results to return (default: 5, max: 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch and extract text from a specific URL. "
            "Use when you have a specific page to read (competitor pricing, docs, articles)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "focus": {"type": "string", "description": "What to focus on extracting from the page"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "document_parse",
        "description": (
            "Parse and extract text from a document at a URL (PDF, article, report). "
            "Returns clean text suitable for analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL of the document to parse"},
                "what_to_extract": {"type": "string", "description": "What information to extract"},
            },
            "required": ["url", "what_to_extract"],
        },
    },
    {
        "name": "structured_extract",
        "description": (
            "Extract structured information from raw text into a clean format. "
            "Use after fetching/searching to pull out specific fields like pricing, features, names, dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Raw text to extract from"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of fields to extract, e.g. ['company_name', 'pricing', 'features']",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "markdown", "bullets"],
                    "description": "Output format (default: markdown)",
                },
            },
            "required": ["text", "fields"],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def web_search(
    query: str,
    api_key: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Brave Search API — structured results, clean for LLM consumption.
    1,000 free searches/month. Docs: https://api.search.brave.com/
    """
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        params = {
            "q": query,
            "count": max(1, min(max_results, 20)),
            "search_lang": "en",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10, verify="/etc/ssl/cert.pem")
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("web", {}).get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("description", "")[:500],
            })

        # Brave also returns a "summary" in some plans
        answer = data.get("summarizer", {}).get("summary", "")

        return {
            "success": True,
            "query": query,
            "answer": answer,
            "results": results,
            "result_count": len(results),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "query": query}


def web_fetch(url: str, focus: str = "") -> dict[str, Any]:
    """Fetch and clean text from a URL. SSL uses macOS system trust store."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BOWEN-SCOUT/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15, verify="/etc/ssl/cert.pem")
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)[:10000]

        return {"success": True, "url": url, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}


def document_parse(url: str, what_to_extract: str = "") -> dict[str, Any]:
    """Parse a document URL — delegates to web_fetch with extraction hint."""
    result = web_fetch(url, focus=what_to_extract)
    if result["success"]:
        result["extraction_goal"] = what_to_extract
    return result


def structured_extract(
    text: str,
    fields: list[str],
    format: str = "markdown",
) -> dict[str, Any]:
    """
    Signal to Claude that it should extract specific fields from the provided text.
    The actual extraction happens in SCOUT's tool_use loop via Claude's response.
    """
    return {
        "success": True,
        "fields_requested": fields,
        "format": format,
        "text_length": len(text),
        "text_preview": text[:300],
        "note": "Use the text above to extract the requested fields and format the response.",
    }


# ── Registry entry ────────────────────────────────────────────────────────────

def make_scout_tool_map(brave_api_key: str) -> dict:
    """Returns tool map with Brave API key bound."""
    return {
        "web_search":        lambda **kw: web_search(api_key=brave_api_key, **kw),
        "web_fetch":         web_fetch,
        "document_parse":    document_parse,
        "structured_extract": structured_extract,
    }
