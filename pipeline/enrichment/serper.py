"""Serper.dev search — structured LinkedIn lookup, no scraping.

The free-search wall (Bing obfuscates, DDG/Mojeek/SearXNG block, Google CSE needs
billing) is beaten by Serper.dev's Google Search API: a keyed POST returns organic
result URLs as clean JSON. We query `site:linkedin.com/in "name" firm`, take the
/in/ profile URL, and verify the slug name-matches the principal — a personal reach
route labeled `inferred` (search-found, not verified by fetching the profile).

A committed daily query counter guards Serper credit spend (shared across scheduled
runs); graceful no-op without SERPER_API_KEY.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Optional

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.ontology import Status, RouteType

QUOTA_PATH = os.path.join("data", "state", "serper_quota.json")
_IN = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-_%]+)", re.I)


def _slug_matches(url: str, name: str) -> bool:
    m = _IN.search(url or "")
    if not m:
        return False                       # not a /in/ profile (e.g. /company/)
    slug = m.group(1).lower()
    toks = [t for t in re.split(r"[^a-z]+", (name or "").lower()) if len(t) >= 3]
    return len(toks) >= 2 and toks[0] in slug and toks[-1] in slug


# --- daily query cap (spend guard for Serper credits) --------------------------
def _load_quota(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def daily_quota_ok(path: str = QUOTA_PATH, limit: int = 100) -> bool:
    q = _load_quota(path)
    if q.get("date") != date.today().isoformat():
        return True                        # new day resets the count
    return q.get("count", 0) < limit


def bump_quota(path: str = QUOTA_PATH) -> None:
    today = date.today().isoformat()
    q = _load_quota(path)
    if q.get("date") != today:
        q = {"date": today, "count": 0}
    q["count"] = q.get("count", 0) + 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(q, f)


def find_person_linkedin(name: str, firm: str, client) -> Optional[str]:
    """First search result on a /in/ profile whose slug name-matches the principal."""
    for url in client.search(f'site:linkedin.com/in "{name}" {firm}') or []:
        if _slug_matches(url, name):
            return re.sub(r"\?.*$", "", url)     # drop tracking params
    return None


# Hosts that are never a firm's OWN website — search aggregators, registries,
# directories, social. A Serper result on one of these is not the firm's site.
_NON_FIRM_HOSTS = (
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "wikipedia.org", "sec.gov", "sec.report", "finra.org",
    "brokercheck.finra.org", "adviserinfo.sec.gov", "bloomberg.com",
    "crunchbase.com", "zoominfo.com", "pitchbook.com", "whalewisdom.com",
    "dnb.com", "opencorporates.com", "projects.propublica.org", "propublica.org",
    "guidestar.org", "causeiq.org", "bizapedia.com", "buzzfile.com",
    "manta.com", "yelp.com", "mapquest.com", "glassdoor.com", "indeed.com",
    "google.com", "bing.com", "wsj.com", "reuters.com", "forbes.com",
)


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url if "//" in url else "//" + url).netloc or "").lower()


def find_company_website(name: str, client,
                         nonfirm=_NON_FIRM_HOSTS) -> Optional[str]:
    """Best-guess official website for a name-only firm via Serper (works from any
    IP, unlike the rendered-Bing finder that CI datacenter IPs get blocked on).

    Returns the first organic result whose host is not a search aggregator /
    registry / social site. The CALLER must still name-match the fetched page
    before trusting it (an aggregator that slips through has no distinctive
    firm tokens and is dropped there)."""
    if not name:
        return None
    for url in client.search(f'{name} family office official website') or []:
        h = _host(url)
        if h and not any(bad in h for bad in nonfirm):
            scheme = "https" if url.startswith("https") else "http"
            return f"{scheme}://{h}"
    return None


def enrich_serper(firm: CandidateFirm, client) -> CandidateFirm:
    if firm.principal_name.is_blank() or not firm.principal_linkedin.is_blank():
        return firm
    li = find_person_linkedin(firm.principal_name.value, firm.firm_name, client)
    if li:
        firm.principal_linkedin = Cell(
            value=li, source="Serper.dev (Google results, linkedin.com/in)",
            method="found via Serper.dev Google search scoped to linkedin.com/in; "
                   "slug name-matched to the principal; not verified by fetching "
                   "the profile",
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            status=Status.INFERRED, route=RouteType.PERSONAL)
    return firm


class Serper:
    """Live Serper.dev Google Search client. Needs SERPER_API_KEY."""

    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None,
                 quota_path: str = QUOTA_PATH, daily_limit: int = 100):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        self.quota_path = quota_path
        self.daily_limit = daily_limit

    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[str]:
        if not self.enabled() or not daily_quota_ok(self.quota_path, self.daily_limit):
            return []
        import requests
        try:
            bump_quota(self.quota_path)     # count the query against the daily cap
            r = requests.post(self.ENDPOINT, timeout=15,
                              headers={"X-API-KEY": self.api_key,
                                       "Content-Type": "application/json"},
                              data=json.dumps({"q": query, "num": 5}))
            if not r.ok:
                return []
            return [it.get("link", "") for it in r.json().get("organic", [])]
        except requests.RequestException:
            return []
