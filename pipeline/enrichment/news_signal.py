"""Per-firm recent-activity signal + principal name from Google News (keyless).

The dataset's commercial value leans on current, dated signals ("why now") and
on the decision-maker's identity. A targeted news query per firm delivers both:
the most recent headline is a dated signal, and family-office headlines routinely
name the principal ("Stanley Druckenmiller's Duquesne Family Office", "X Family
Office hires Y as CIO").

Everything here is INFERENCE at best (a headline is not a filing), so it is
stamped low/medium confidence and must survive validation. A name we cannot
extract cleanly is left blank, never guessed.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from pipeline.discovery.base import DiscoverySource
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

# classify the signal from headline verbs
SIGNAL_TYPES = [
    ("hire", ("hires", "appoints", "names", "joins", "recruits", "taps")),
    ("investment", ("invests", "backs", "acquires", "buys", "stake", "leads round")),
    ("fund", ("fund", "commits", "raises", "launches")),
    ("news", ()),  # default
]

# A short human name, used inside the patterns below. Lazy surname repetition so
# it stops at the real last name instead of swallowing a trailing verb/gerund
# ("Robert Soros Stepping" -> "Robert Soros").
_NM = r"[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+){1,2}?"


def _classify(title: str) -> str:
    low = title.lower()
    for label, words in SIGNAL_TYPES:
        if any(w in low for w in words):
            return label
    return "news"


_APOS = r"['’‘`]"  # ' ’ ‘ ` variants Google News uses


def extract_principal_from_headline(title: str, firm_name: str) -> Optional[str]:
    """Pull a principal's name from a headline when a clear pattern matches.

    Ordered most-reliable first. All matches are still INFERENCE (a headline is
    not a filing) and left for validation to confirm/qualify.
    """
    stem = re.escape(firm_name.split(" Family Office")[0].strip())
    patterns = [
        # "Stanley Druckenmiller's Duquesne Family Office"
        rf"({_NM}){_APOS}s\s+{stem}",
        # "Jeff Bezos' family office" — possessive directly on "family office"
        rf"({_NM}){_APOS}s?\s+[Ff]amily\s+[Oo]ffice",
        # "X Family Office hires/appoints/names Jane Doe"
        rf"{stem}[^.]*?\b(?:[Hh]ires|[Aa]ppoints|[Nn]ames|[Tt]aps|[Rr]ecruits)\s+({_NM})",
        # "Robert Soros ... President of Soros Family Office"
        rf"({_NM})\b[^,.]*?\b[Oo]f\s+(?:the\s+)?{stem}",
    ]
    for pat in patterns:
        m = re.search(pat, title)
        if m:
            name = m.group(1).strip()
            # reject if it's just the firm's own words, or a single token
            if len(name.split()) >= 2 and name.lower() not in firm_name.lower():
                return name
    return None


class NewsSignalEnricher:
    def __init__(self):
        self._http = DiscoverySource()

    def _latest(self, firm_name: str) -> Optional[Tuple[str, str, str]]:
        q = f'"{firm_name}"'
        try:
            r = self._http.get(RSS.format(q=quote_plus(q)))
            root = ET.fromstring(r.content)
        except Exception as e:
            print(f"[news_signal] {firm_name}: {e}")
            return None
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            # require the firm name to actually appear (avoid loose matches)
            if firm_name.split(" Family Office")[0].split()[0].lower() in title.lower():
                return title, link, pub
        return None

    def enrich(self, firm: CandidateFirm) -> CandidateFirm:
        hit = self._latest(firm.firm_name)
        if not hit:
            return firm
        title, link, pub = hit
        asof = pub[:16]
        # Only overwrite the news signal if we don't already have a fresher one.
        if firm.recent_signal.is_blank():
            firm.recent_signal = Cell(
                value=title, source=link, method="targeted news query",
                epistemic=Epistemic.INFERENCE, confidence=Confidence.LOW,
                asof_date=asof,
            )
            firm.signal_date = asof
            firm.signal_type = _classify(title)
        # principal name from the headline, if a clear pattern matched
        if firm.principal_name.is_blank():
            name = extract_principal_from_headline(title, firm.firm_name)
            if name:
                firm.principal_name = Cell(
                    value=name, source=link,
                    method="named in news headline (unverified)",
                    epistemic=Epistemic.INFERENCE, confidence=Confidence.LOW,
                    asof_date=asof,
                )
        return firm


def enrich_news_all(pool):
    enr = NewsSignalEnricher()
    for i, firm in enumerate(pool, 1):
        try:
            enr.enrich(firm)
        except Exception as e:
            print(f"[news_signal] {firm.firm_name}: {e}")
        if i % 20 == 0:
            print(f"[news_signal] {i}/{len(pool)} done")
    return pool
