"""Website lookup via Google Programmable Search (free tier, no credit card).

This is the *real search* fallback chosen after DuckDuckGo was blocked in this
environment and after I rejected domain-guessing (see DECISIONS.md). It only
activates when GOOGLE_API_KEY + GOOGLE_CSE_ID are set in the environment; with
no keys it returns None so the pipeline stays honest and never invents a URL.

Free tier: 100 queries/day. Results are cached (shared cache with the DDG
finder) so a firm is never looked up twice.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()  # pick up GOOGLE_API_KEY / GOOGLE_CSE_ID from a local .env

# reuse the shared cache + domain rules so both finders behave identically
from pipeline.enrichment.website_finder import BLOCK, _CACHE, _save_cache, _domain

ENDPOINT = "https://www.googleapis.com/customsearch/v1"


# Circuit breaker: once Google returns a hard access error (e.g. API not yet
# propagated / throttled), stop querying for the rest of the run instead of
# hammering a blocked endpoint 200+ times.
_DISABLED = False


def _keys() -> Optional[tuple]:
    if _DISABLED:
        return None
    api = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_ID")
    return (api, cx) if api and cx else None


def find_website_google(firm_name: str) -> Optional[str]:
    """Return the firm's official homepage via Google search, or None.

    None when: no keys configured, request fails, or no non-blocked result.
    Cached per firm_name (shares the DDG finder's cache).
    """
    key = firm_name.strip().lower()
    if key in _CACHE:
        return _CACHE[key] or None

    creds = _keys()
    if not creds:
        return None  # no keys -> stay honest, do nothing
    api, cx = creds

    params = {"key": api, "cx": cx,
              "q": f"{firm_name} family office official website", "num": 5}
    global _DISABLED
    try:
        r = requests.get(ENDPOINT, params=params, timeout=30)
        if r.status_code == 403:
            _DISABLED = True  # trip the breaker; API not accessible this run
            print(f"[google_search] 403 access denied -> disabling Google lookups for this run")
            return None
        r.raise_for_status()
        items = r.json().get("items", []) or []
    except Exception as e:
        print(f"[google_search] '{firm_name}': {e}")
        return None  # don't cache transient failures

    result = None
    for it in items:
        link = it.get("link") or ""
        if not urlparse(link).scheme:
            continue
        if any(b in _domain(link) for b in BLOCK):
            continue
        result = f"{urlparse(link).scheme}://{urlparse(link).netloc}"
        break

    _CACHE[key] = result or ""
    _save_cache(_CACHE)
    return result
