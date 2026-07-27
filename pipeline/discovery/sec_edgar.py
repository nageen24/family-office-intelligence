"""Discovery via SEC EDGAR full-text search (free, official).

SEC's EFTS endpoint returns JSON hits for filings mentioning a phrase. Firms
that file with the SEC and describe themselves as a "family office" surface
here. Note the domain insight (DECISIONS.md): true SFOs are often EXEMPT from
SEC registration, so this source skews toward MFOs and registered advisers —
we use it for existence/AUM proof more than for finding hidden SFOs.
"""
from __future__ import annotations

from typing import List

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm

EFTS = "https://efts.sec.gov/LATEST/search-index?q=%22family+office%22"


@register
class SecEdgar(DiscoverySource):
    name = "SEC EDGAR full-text search"
    job = "discovery + existence proof"

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        try:
            r = self.get(EFTS)
            data = r.json()
        except Exception as e:  # network / format issues logged, not fatal
            print(f"[{self.name}] error: {e}")
            return out

        hits = (data.get("hits", {}) or {}).get("hits", [])
        seen = set()
        for h in hits[: limit * 2]:
            src = h.get("_source", {})
            names = src.get("display_names") or []
            for nm in names:
                clean = nm.split("(")[0].strip()
                if clean and clean.lower() not in seen:
                    seen.add(clean.lower())
                    out.append(CandidateFirm(
                        firm_name=clean,
                        discovery_source=self.name,
                    ))
            if len(out) >= limit:
                break
        return out[:limit]
