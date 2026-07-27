"""Discovery via Google News RSS (free, no key).

News surfaces ACTIVE family offices — "the family office of X invested in..."
or "X Family Office hires..." — which also yields the dated recent-activity
signals the dataset values. Firm-name extraction here is heuristic; the firm
must still be proven in validation (Rule 2).
"""
from __future__ import annotations

import re
from typing import List
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
]
# Pull a plausible firm name ending in "Family Office" / "Capital" / "Partners".
NAME_RE = re.compile(
    r"([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,3}\s+"
    r"(?:Family Office|Capital|Partners|Holdings|Investments|Ventures))"
)


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
                m = NAME_RE.search(title)
                if not m:
                    continue
                nm = m.group(1).strip()
                if nm.lower() in seen:
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
