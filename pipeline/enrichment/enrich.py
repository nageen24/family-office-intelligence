"""Enrichment: fill high-value cells for each discovered firm.

Strategy (free, ToS-respecting):
1. Find the firm's website (if not already known) via a lightweight web search.
2. Fetch the site's homepage + likely "about"/"team"/"contact" pages.
3. Extract: description/background, investing language (thesis/mandate hints),
   emails, phones, principal names/titles, corporate LinkedIn.

Everything extracted here is a CANDIDATE value. It is not trusted until the
validation stage stamps provenance/confidence and cross-checks it. We never
invent a value: if a page doesn't yield it, the cell stays blank.
"""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from pipeline.discovery.base import DiscoverySource  # for session/UA reuse
from pipeline.enrichment.website_finder import find_website
from pipeline.enrichment.sec_filing import enrich_from_sec
from pipeline.enrichment.news_signal import NewsSignalEnricher
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,2}[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9\-_%]+")
THESIS_WORDS = ("invest", "focus", "sector", "strategy", "portfolio",
                "allocation", "direct", "private", "venture", "real estate")
# mandate = concrete deal criteria (what/where/how much they deploy)
MANDATE_WORDS = ("seek", "target", "criteria", "check size", "ticket",
                 "stage", "geograph", "minimum", "we look for", "we invest in",
                 "mandate", "deploy", "opportunit", "acquire", "partner with")
# AUM figure: "$1.2 billion", "$500 million", "$3bn" etc.
AUM_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:trillion|billion|million|bn|mn|tn|b|m)\b",
    re.I,
)
AUM_CONTEXT = ("asset", "aum", "manage", "under management", "capital")

_http = DiscoverySource()  # reuse its polite session


def _extract_aum(page_text: str) -> Optional[str]:
    """Return an AUM figure only when it sits near asset/AUM/manage language.

    A raw dollar figure alone (a deal size, a price) is not AUM, so we require
    nearby context — otherwise the cell stays blank (honest over fake).
    """
    low = page_text.lower()
    for m in AUM_RE.finditer(page_text):
        window = low[max(0, m.start() - 60): m.end() + 60]
        if any(w in window for w in AUM_CONTEXT):
            return m.group(0).strip()
    return None


def _fetch(url: str) -> Optional[BeautifulSoup]:
    try:
        r = _http.get(url)
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def _first(regex, text) -> Optional[str]:
    m = regex.search(text or "")
    return m.group(0) if m else None


def enrich_firm(firm: CandidateFirm) -> CandidateFirm:
    url = firm.website
    if not url:
        # Try to find the official site (DuckDuckGo, cached). Many genuine SFOs
        # have none — that returns None and the cell stays an honest blank.
        url = find_website(firm.firm_name)
        if url:
            firm.website = url
    if not url:
        return firm
    if not url.startswith("http"):
        url = "https://" + url

    soup = _fetch(url)
    if soup is None:
        return firm

    page_text = soup.get_text(" ", strip=True)
    html = str(soup)

    # background / description
    meta = soup.find("meta", attrs={"name": "description"})
    desc = meta.get("content") if meta and meta.get("content") else page_text[:400]
    if desc:
        firm.background = Cell(value=desc.strip(), source=url,
                               method="site homepage / meta description",
                               epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)

    # AUM (only when near asset/AUM/manage language)
    aum = _extract_aum(page_text)
    if aum:
        firm.aum = Cell(value=aum, source=url,
                        method="site copy near AUM/assets language (unverified)",
                        epistemic=Epistemic.INFERENCE, confidence=Confidence.LOW)

    # investing thesis hint
    for p in soup.find_all(["p", "li"]):
        t = p.get_text(" ", strip=True)
        if len(t) > 60 and sum(w in t.lower() for w in THESIS_WORDS) >= 2:
            firm.investing_thesis = Cell(value=t[:300], source=url,
                                         method="site copy (investing language)",
                                         epistemic=Epistemic.INFERENCE,
                                         confidence=Confidence.LOW)
            break

    # investing mandate (what/where/how they deploy — criteria language)
    for p in soup.find_all(["p", "li"]):
        t = p.get_text(" ", strip=True)
        if len(t) > 50 and sum(w in t.lower() for w in MANDATE_WORDS) >= 2:
            firm.mandate = Cell(value=t[:300], source=url,
                                method="site copy (mandate/criteria language)",
                                epistemic=Epistemic.INFERENCE,
                                confidence=Confidence.LOW)
            break

    # contacts
    email = _first(EMAIL_RE, html)
    if email:
        firm.principal_email = Cell(value=email.lower(), source=url,
                                    method="scraped from site (unverified)",
                                    epistemic=Epistemic.INFERENCE,
                                    confidence=Confidence.LOW)
    phone = _first(PHONE_RE, page_text)
    if phone:
        firm.principal_phone = Cell(value=phone.strip(), source=url,
                                    method="scraped from site (unverified)",
                                    epistemic=Epistemic.INFERENCE,
                                    confidence=Confidence.LOW)
    li = _first(LINKEDIN_RE, html)
    if li:
        if "/company" in li:
            firm.corporate_linkedin = li
        else:
            firm.principal_linkedin = Cell(value=li, source=url,
                                           method="linked from site",
                                           epistemic=Epistemic.FACT,
                                           confidence=Confidence.MEDIUM)
    return firm


def enrich_all(pool: List[CandidateFirm]) -> List[CandidateFirm]:
    news = NewsSignalEnricher()
    for i, firm in enumerate(pool, 1):
        try:
            enrich_from_sec(firm)   # official filing data first (no key, no guess)
            news.enrich(firm)       # recent dated signal + principal from news (keyless)
            enrich_firm(firm)       # then website scrape (needs a found site)
        except Exception as e:
            print(f"[enrich] {firm.firm_name}: {e}")
        if i % 10 == 0:
            print(f"[enrich] {i}/{len(pool)} done")
    return pool
