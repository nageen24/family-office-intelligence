"""Discovery via SEC EDGAR full-text search (free, official).

SEC's EFTS endpoint returns JSON hits for filings mentioning a phrase. Firms
that file with the SEC and describe themselves as a "family office" surface
here. Note the domain insight (DECISIONS.md): true SFOs are often EXEMPT from
SEC registration, so this source skews toward MFOs and registered advisers —
we use it for existence/AUM proof more than for finding hidden SFOs.
"""
from __future__ import annotations

from typing import List

from urllib.parse import quote_plus

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm

EFTS = "https://efts.sec.gov/LATEST/search-index?q={q}&from={frm}"
# Wide net (option 1): several phrasings + pagination for more real throughput.
# Validation (Rule 2) is the filter that drops the big filers who merely
# mention the phrase; that rejection is the point (see DECISIONS.md).
PHRASES = ['"family office"', '"single family office"', '"multi family office"']


@register
class SecEdgar(DiscoverySource):
    name = "SEC EDGAR full-text search"
    job = "discovery + existence proof"

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        seen = set()
        for phrase in PHRASES:
            for frm in (0, 10, 20, 30):  # EFTS returns ~10 hits/page
                if len(out) >= limit:
                    return out[:limit]
                url = EFTS.format(q=quote_plus(phrase), frm=frm)
                try:
                    data = self.get(url).json()
                except Exception as e:  # network / format issues logged, not fatal
                    print(f"[{self.name}] error on {phrase} from={frm}: {e}")
                    break
                hits = (data.get("hits", {}) or {}).get("hits", [])
                if not hits:
                    break
                for h in hits:
                    names = (h.get("_source", {}) or {}).get("display_names") or []
                    for nm in names:
                        clean = nm.split("(")[0].strip()
                        if clean and clean.lower() not in seen:
                            seen.add(clean.lower())
                            out.append(CandidateFirm(
                                firm_name=clean,
                                discovery_source=self.name,
                            ))
        return out[:limit]
