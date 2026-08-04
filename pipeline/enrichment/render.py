"""Headless-browser layer (Playwright) — used ONLY where the static path fails.

Two jobs the $0 static path can't do:
  1. render JS-built team/people pages so LinkedIn profile links become visible;
  2. find a website for a name-only firm (EDGAR/News/CIK/990) via a rendered Bing
     search — a real browser gets past the datacenter-IP block that defeats
     scripted search.

Everything here is graceful: if Playwright or Chromium isn't available, each
function returns empty and the caller falls back to static behaviour, so the
pipeline never hard-depends on the browser.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, quote_plus

_LI_IN = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+", re.I)

# hosts that are never a firm's own website in a search result
_NON_FIRM = ("bing.com", "microsoft.com", "google.com", "linkedin.com",
             "facebook.com", "twitter.com", "x.com", "instagram.com",
             "youtube.com", "wikipedia.org", "sec.gov", "bloomberg.com",
             "crunchbase.com", "zoominfo.com", "sec.report", "adviserinfo.sec.gov")


def available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        return False


def _with_page(fn, timeout: int = 20000):
    """Run fn(page) in a throwaway headless Chromium (thread-safe, self-contained)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0 Safari/537.36"))
                page.set_default_timeout(timeout)
                return fn(page)
            finally:
                browser.close()
    except Exception:
        return None


def render_text(url: str, max_chars: int = 9000) -> str:
    """Rendered visible text of a page + any LinkedIn /in profile URLs it links."""
    def _do(page):
        page.goto(url, wait_until="networkidle")
        body = page.inner_text("body")
        html = page.content()
        links = " ".join(dict.fromkeys(_LI_IN.findall(html)))
        return (body[:max_chars] + " " + links).strip()
    return _with_page(_do) or ""


def find_website(firm_name: str) -> Optional[str]:
    """Best-guess official website via a rendered Bing search for the firm.

    Returns the first organic result on a plausible firm domain; the CALLER must
    still verify it (name-match on the fetched page) before trusting it."""
    if not firm_name:
        return None
    query = quote_plus(f"{firm_name} family office official site")

    def _do(page):
        page.goto(f"https://www.bing.com/search?q={query}", wait_until="domcontentloaded")
        hrefs = page.eval_on_selector_all(
            "li.b_algo h2 a", "els => els.map(e => e.href)")
        for h in hrefs or []:
            host = (urlparse(h).netloc or "").lower()
            if host and not any(bad in host for bad in _NON_FIRM):
                return f"{urlparse(h).scheme}://{host}"
        return None
    return _with_page(_do)
