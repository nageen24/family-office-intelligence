"""Discovery via ProPublica Nonprofit Explorer (free API).

Family foundations file Form 990 and often share staff, address, and
principals with the family's single-family office. This is a back-door to
INVISIBLE SFOs that have no website or marketing (DECISIONS.md). Good for
discovery; weak on current contacts — those need enrichment elsewhere.
"""
from __future__ import annotations

from typing import List

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm

API = "https://projects.propublica.org/nonprofits/api/v2/search.json"


@register
class ProPublica990(DiscoverySource):
    name = "ProPublica Nonprofit Explorer (Form 990)"
    job = "discovery (hidden SFO via family foundations)"

    QUERIES = ["family foundation", "family office", "family trust"]

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        seen = set()
        for q in self.QUERIES:
            try:
                r = self.get(API, params={"q": q})
                data = r.json()
            except Exception as e:
                print(f"[{self.name}] error on '{q}': {e}")
                continue
            for org in data.get("organizations", []):
                nm = (org.get("name") or "").strip()
                if not nm or nm.lower() in seen:
                    continue
                seen.add(nm.lower())
                firm = CandidateFirm(firm_name=nm, discovery_source=self.name)
                city = org.get("city")
                state = org.get("state")
                if city or state:
                    firm.hq_location = ", ".join([x for x in [city, state] if x])
                out.append(firm)
                if len(out) >= limit:
                    return out
        return out
