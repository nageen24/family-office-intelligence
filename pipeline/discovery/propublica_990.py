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

    QUERIES = ["family office", "family foundation", "family trust",
               "family capital", "family investment office"]

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        out: List[CandidateFirm] = []
        seen = set()
        for q in self.QUERIES:
            for page in range(0, 3):  # API pages of ~25; widen throughput
                if len(out) >= limit:
                    return out
                try:
                    data = self.get(API, params={"q": q, "page": page}).json()
                except Exception as e:
                    print(f"[{self.name}] error on '{q}' page {page}: {e}")
                    break
                orgs = data.get("organizations", [])
                if not orgs:
                    break
                for org in orgs:
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
