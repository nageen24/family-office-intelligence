"""Find a firm's official website via DuckDuckGo's free HTML endpoint.

Chosen over paid/keyed search and over LinkedIn/Google scraping because it needs
no key and doesn't violate ToS — consistent with the rest of this $0 build
(see DECISIONS.md, enrichment-website-lookup decision).

Guards:
- Results are cached to disk so we never re-query the same firm.
- Polite delay between queries; browser-like UA (DDG rejects bare bots).
- Social / aggregator / news domains are rejected — we want the firm's OWN site,
  not its LinkedIn or a news article about it.
- Honest blank: if nothing plausible is found, return None (never invent a URL).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

DDG = "https://html.duckduckgo.com/html/?q={q}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

CACHE_PATH = Path("data/interim/website_cache.json")

# Domains that are never a firm's own official site.
BLOCK = (
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "wikipedia.org", "bloomberg.com", "crunchbase.com",
    "sec.gov", "propublica.org", "opencorporates.com", "google.com",
    "duckduckgo.com", "reuters.com", "wsj.com", "forbes.com", "ft.com",
    "prnewswire.com", "businesswire.com", "yahoo.com", "medium.com",
    "glassdoor.com", "indeed.com", "zoominfo.com", "dnb.com", "pitchbook.com",
)

_session = requests.Session()
_session.headers.update({"User-Agent": UA})


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1), encoding="utf-8")


_CACHE = _load_cache()


def _decode_ddg_href(href: str) -> Optional[str]:
    """DDG wraps results as //duckduckgo.com/l/?uddg=<encoded-url>."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
        return None
    if parsed.scheme in ("http", "https"):
        return href
    return None


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def find_website(firm_name: str, *, delay: float = 1.5) -> Optional[str]:
    """Return the firm's best-guess official homepage URL, or None.

    Cached per firm_name. A None result is cached too (as "") so we don't retry
    a firm that genuinely has no findable site.
    """
    key = firm_name.strip().lower()
    if key in _CACHE:
        return _CACHE[key] or None

    query = f'{firm_name} family office official website'
    try:
        r = _session.get(DDG.format(q=quote_plus(query)), timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[website_finder] '{firm_name}': search failed: {e}")
        return None  # don't cache transient failures

    soup = BeautifulSoup(r.text, "html.parser")
    result = None
    for a in soup.select("a.result__a"):
        href = a.get("href") or ""
        url = _decode_ddg_href(href)
        if not url:
            continue
        dom = _domain(url)
        if any(b in dom for b in BLOCK):
            continue
        result = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        break

    _CACHE[key] = result or ""
    _save_cache(_CACHE)
    time.sleep(delay)  # be polite to DDG
    return result
