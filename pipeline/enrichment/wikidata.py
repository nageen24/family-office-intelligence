"""Resolve a firm's official website via Wikidata (keyless, no abuse-block risk).

Chosen over Google Custom Search after Google's abuse system IP-blocked us
(see DECISIONS.md). Wikidata exposes an entity's official website as property
P856 — structured, free, no key, and it doesn't share Google's abuse detection.
Coverage skews to well-known firms; smaller single-family offices often aren't
in Wikidata at all, which returns an honest None (never a guess).

Flow: wbsearchentities (name -> QID) -> wbgetclaims P856 (QID -> URL).
Polite: identifying User-Agent (Wikimedia requires it) + a small delay.
"""
from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlparse

import requests

API = "https://www.wikidata.org/w/api.php"
UA = "family-office-research/0.1 (contact: nageenabid0624@gmail.com)"

# entity descriptions that mean the top hit is NOT the firm we want
BAD_DESC = ("film", "song", "album", "given name", "family name", "surname",
            "human settlement", "village", "town", "city", "county", "genus",
            "species", "university", "college", "school", "footballer",
            "politician", "actor", "musician", "singer", "writer", "river",
            "mountain", "born ", "american businessman", "businessperson",
            # tech/other entities that share a firm's acronym (PMG -> Proxmox
            # Mail Gateway "management software" slipped the finance filter)
            "software", "hardware", "application", "operating system",
            "protocol", "video game", "programming", "website", "web browser",
            "disease", "condition", "medal", "award", "band", "airport")

# the top hit must look like a finance/company entity to be trusted — this is
# what stops "Duquesne Family Office" -> "Duquesne University" (duq.edu).
GOOD_DESC = ("investment", "holding", "firm", "office", "capital",
             "management", "financial", "finance", "private", "asset",
             "wealth", "fund", "company", "corporation", "equity", "advisor",
             "advisory", "enterprise", "conglomerate", "bank")

_session = requests.Session()
_session.headers.update({"User-Agent": UA})


def _search_qid(name: str) -> Optional[tuple]:
    try:
        r = _session.get(API, params={
            "action": "wbsearchentities", "search": name, "language": "en",
            "format": "json", "type": "item", "limit": 1}, timeout=30)
        r.raise_for_status()
        hits = r.json().get("search", [])
    except Exception as e:
        print(f"[wikidata] search '{name}': {e}")
        return None
    if not hits:
        return None
    return hits[0]["id"], (hits[0].get("description") or "").lower()


def _p856(qid: str) -> Optional[str]:
    try:
        r = _session.get(API, params={
            "action": "wbgetclaims", "entity": qid, "property": "P856",
            "format": "json"}, timeout=30)
        r.raise_for_status()
        claims = r.json().get("claims", {}).get("P856", [])
    except Exception as e:
        print(f"[wikidata] claims {qid}: {e}")
        return None
    if not claims:
        return None
    try:
        return claims[0]["mainsnak"]["datavalue"]["value"]
    except (KeyError, IndexError):
        return None


def find_website_wikidata(firm_name: str, *, delay: float = 0.5) -> Optional[str]:
    """Return the firm's official website from Wikidata P856, or None."""
    # Try the full name, then the name without a "Family Office" suffix.
    candidates = [firm_name]
    stem = firm_name.split(" Family Office")[0].strip()
    # Skip a stem that is a short/acronym token — "PMG", "CVA", "AC" collide
    # with unrelated entities (Proxmox Mail Gateway, etc.). Only stem-search a
    # distinctive multi-word or long name.
    if stem and stem != firm_name and len(stem) >= 5 and " " in stem:
        candidates.append(stem)

    for cand in candidates:
        hit = _search_qid(cand)
        time.sleep(delay)
        if not hit:
            continue
        qid, desc = hit
        if any(b in desc for b in BAD_DESC):
            continue  # top hit is a person/place/film/university, not the firm
        # require positive company-like evidence (guards against stem collisions)
        if desc and not any(g in desc for g in GOOD_DESC):
            continue
        url = _p856(qid)
        time.sleep(delay)
        if url and urlparse(url).scheme in ("http", "https"):
            return f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    return None
