"""Discovery via Wikidata SPARQL — non-SEC, provable family offices.

The SEC-heavy pool misses family offices that never file 13F — including the
invisible single-family offices the assessment prizes. Wikidata carries a
structured, citable class for them: instance-of (P31) "family office" (Q751314).
That P31 claim is independent affirmative evidence a firm is a family office
(Rule 2) — not the firm's own name — and P856 gives the official website, which
also satisfies the existence gate. Coverage is small (well-known offices only,
e.g. Michael Dell's DFO Management, Lukas Walton's Builders Vision), but every
hit is a real, non-SEC record that widens the discovery base.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

SPARQL = "https://query.wikidata.org/sparql"
QUERY = """SELECT ?item ?itemLabel ?website ?countryLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q751314 .
  OPTIONAL { ?item wdt:P856 ?website. }
  OPTIONAL { ?item wdt:P17 ?country. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 300"""


@register
class WikidataFamilyOffices(DiscoverySource):
    name = "Wikidata (P31: family office)"
    job = "discovery (non-SEC provable FOs, incl. hidden SFOs)"

    def discover(self, limit: int = 60) -> List[CandidateFirm]:
        try:
            data = self.get(SPARQL, params={"query": QUERY, "format": "json"}).json()
        except Exception as e:
            print(f"[{self.name}] SPARQL error: {e}")
            return []
        out: List[CandidateFirm] = []
        seen = set()
        for b in data.get("results", {}).get("bindings", []):
            nm = (b.get("itemLabel", {}).get("value") or "").strip()
            qid = b.get("item", {}).get("value", "")
            # skip WSJ-article-style items and blank/duplicate names
            if not nm or nm.lower() in seen or nm.startswith("Q") or len(nm) > 60:
                continue
            seen.add(nm.lower())
            firm = CandidateFirm(firm_name=nm, discovery_source=self.name)
            web = b.get("website", {}).get("value")
            if web and urlparse(web).scheme in ("http", "https"):
                firm.website = f"{urlparse(web).scheme}://{urlparse(web).netloc}"
            firm.hq_location = b.get("countryLabel", {}).get("value") or None
            # Independent structured evidence it's a family office (Rule 2 basis).
            firm.background = Cell(
                value="Classified as a family office on Wikidata "
                      "(instance of Q751314 'family office').",
                source=qid, method="Wikidata P31 claim",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)
            out.append(firm)
            if len(out) >= limit:
                break
        return out
