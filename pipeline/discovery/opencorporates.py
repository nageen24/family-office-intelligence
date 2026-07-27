"""Discovery/entity-proof via OpenCorporates (free tier, rate-limited).

OpenCorporates aggregates official company-registry data across jurisdictions.
Used mainly to confirm a firm is a registered legal entity and to get its
jurisdiction — an existence-proof job more than a discovery job. The free API
is heavily rate-limited; without a token it may return limited results, which
we handle gracefully rather than faking.
"""
from __future__ import annotations

from typing import List

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm

API = "https://api.opencorporates.com/v0.4/companies/search"


@register
class OpenCorporates(DiscoverySource):
    name = "OpenCorporates"
    job = "entity existence proof"

    def discover(self, limit: int = 20) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        try:
            r = self.get(API, params={"q": "family office", "per_page": 30})
            data = r.json()
        except Exception as e:
            # Free tier often 401/403/429 without a token — honest, not fatal.
            print(f"[{self.name}] limited/unavailable on free tier: {e}")
            return out

        results = (data.get("results", {}) or {}).get("companies", [])
        seen = set()
        for item in results:
            c = item.get("company", {})
            nm = (c.get("name") or "").strip()
            if not nm or nm.lower() in seen:
                continue
            seen.add(nm.lower())
            firm = CandidateFirm(firm_name=nm, discovery_source=self.name)
            firm.hq_location = c.get("jurisdiction_code")
            out.append(firm)
            if len(out) >= limit:
                break
        return out
