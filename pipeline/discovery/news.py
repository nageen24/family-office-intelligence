"""Discovery via Google News RSS (free, no key).

News surfaces ACTIVE family offices — "the family office of X invested in..."
or "X Family Office hires..." — which also yields the dated recent-activity
signals the dataset values. Firm-name extraction here is heuristic; the firm
must still be proven in validation (Rule 2).

Extractor note (Session 3 bugfix): the first version grabbed headline
fragments like "How Family Office" or "Venture Capital" because it accepted any
capitalized run ending in a broad suffix. It now only accepts names ending in
"Family Office" and rejects prefixes that are just common headline words
(How/The/Will/Top/...). See DECISIONS.md 2026-07-27 discovery-noise entry.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote_plus

from xml.etree import ElementTree as ET

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
QUERIES = [
    '"family office" invests',
    '"family office" hires',
    '"single family office"',
    '"family office" commits fund',
    '"family office" acquires',
    '"family office" backs',
]

# Only accept a real firm name ending in "Family Office". Broader suffixes
# (Capital/Partners/Ventures) were too noisy in news headlines.
# Real FO names before "Family Office" are short (Duquesne / Dakota Global /
# UBS / Bezos), so cap the prefix at 2 words to cut long headline fragments.
NAME_RE = re.compile(
    r"([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,1})\s+Family Office\b"
)

# Common leading headline words that are NOT part of a firm name.
STOPWORDS = {
    "how", "the", "a", "an", "will", "top", "inside", "helping", "sectors",
    "drivers", "evolution", "what", "why", "when", "this", "these", "best",
    "new", "your", "our", "my", "single", "multi", "global", "us", "uk",
    "leading", "major", "biggest", "largest", "first", "next", "one", "two",
    "of", "and", "for", "with", "into", "from", "meet", "is", "are", "was",
    # common headline verbs / relational fragments seen in real runs
    "departs", "hires", "run", "his", "her", "father", "expands", "acquires",
    "names", "lead", "impact", "newly", "founded", "former", "wealth", "large",
    "management", "mega", "run", "expands", "backs", "invests", "commits",
}


def extract_firm_name(title: str) -> Optional[str]:
    """Pull a plausible '<Name> Family Office' firm name from a headline.

    Pure function so it can be unit-tested without the network. Returns the
    firm name (including 'Family Office') or None when the prefix is only
    generic headline words.
    """
    m = NAME_RE.search(title)
    if not m:
        return None
    prefix = m.group(1).strip()
    prefix_words = prefix.split()
    # Reject if EVERY word before "Family Office" is a generic headline word.
    if all(w.lower() in STOPWORDS for w in prefix_words):
        return None
    # Trim leading stopwords ("The Dakota Global Family Office" -> "Dakota Global Family Office").
    while prefix_words and prefix_words[0].lower() in STOPWORDS:
        prefix_words.pop(0)
    if not prefix_words:
        return None
    return " ".join(prefix_words) + " Family Office"


@register
class GoogleNews(DiscoverySource):
    name = "Google News RSS"
    job = "discovery (active FOs) + dated signals"

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        seen = set()
        for q in QUERIES:
            try:
                r = self.get(RSS.format(q=quote_plus(q)))
                root = ET.fromstring(r.content)
            except Exception as e:
                print(f"[{self.name}] error on '{q}': {e}")
                continue
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                nm = extract_firm_name(title)
                if not nm or nm.lower() in seen:
                    continue
                seen.add(nm.lower())
                firm = CandidateFirm(firm_name=nm, discovery_source=self.name)
                firm.recent_signal = Cell(
                    value=title, source=link, method="news headline",
                    epistemic=Epistemic.INFERENCE, confidence=Confidence.LOW,
                    asof_date=pub[:16],
                )
                out.append(firm)
                if len(out) >= limit:
                    return out
        return out
