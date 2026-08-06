"""S9 — SEC Form ADV registered-adviser roster as the Phase-2 discovery backbone.

The adviserinfo.sec.gov API is IP-blocked from this environment (403, Stage-1
and re-confirmed), but the same data is published as a monthly FOIA roster ZIP on
www.sec.gov, which IS reachable. One CSV lists every SEC-registered adviser with
its OWN website, phone, address, CRD and CIK — existence + reachability + the
site S10 needs to prove FO-function, in one $0 source.

Discovery only NARROWS to plausible family offices; it never asserts function.
The net (user decision: wide): advisers that report high-net-worth individual
clients (Form ADV Item 5.D(b)) and, by default, are concentrated on individuals
(no institutional client types) with a real own website. Every candidate leaves
here as Unresolved-Quarantine until S10 verifies the firm's own site.
"""
from __future__ import annotations

import csv
import io
import os
import zipfile
from typing import List, Optional
from urllib.parse import urlparse

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

DATA_PAGE = ("https://www.sec.gov/data-research/sec-markets-data/"
             "information-about-registered-investment-advisers-exempt-reporting-advisers")
CACHE = os.path.join("data", "interim", "adv_roster.csv")

# Item 5.D institutional client-type counts — presence means the firm is not a
# pure individual/family shop (used to keep the concentrated net tight).
_INSTITUTIONAL = ("5D(d)(1)", "5D(f)(1)", "5D(g)(1)", "5D(k)(1)", "5D(l)(1)")


def _num(row: dict, col: str) -> float:
    v = (row.get(col) or "").replace(",", "").strip()
    try:
        return float(v)
    except ValueError:
        return 0.0


def _real_site(row: dict) -> Optional[str]:
    w = (row.get("Website Address") or "").strip()
    if not w.lower().startswith("http"):
        return None
    host = urlparse(w).netloc.lower()
    if any(s in host for s in ("facebook", "linkedin", "twitter", "instagram", "youtube")):
        return None
    return w


import re as _re
_FO_NAME = _re.compile(
    r"family office|multi.?family|single.?family|family wealth|private wealth|"
    r"family capital|family partners|family enterprise|family group|"
    r"family investment", _re.I)


def _name(row: dict) -> str:
    return f"{row.get('Primary Business Name','')} {row.get('Legal Name','')}"


def select_rows(rows: List[dict], concentrated: bool = True,
                name_net: bool = False) -> List[dict]:
    """FO/MFO candidate net from the roster (every row still needs a real own site).

    - concentrated=True (default): the tight net — serves HNW individuals AND has
      no institutional client types. High precision.
    - concentrated=False: the wide net — serves HNW individuals, institutional
      clients allowed (picks up MFOs / private-wealth arms that also take
      institutional money). ~2x the pool.
    - name_net=True: ALSO keep any firm whose NAME signals a family office
      (family office / multi-family / private wealth / ...) even if it reports no
      HNW-individual clients — a firm calling itself a family office is a
      candidate regardless of its Item 5.D mix. Proof B still gates on the site.
    """
    out = []
    for r in rows:
        if not _real_site(r):                   # must have a real own website
            continue
        named = name_net and bool(_FO_NAME.search(_name(r)))
        if named:
            out.append(r)
            continue
        if _num(r, "5D(b)(1)") <= 0:           # else must serve HNW individuals
            continue
        if concentrated and any(_num(r, c) > 0 for c in _INSTITUTIONAL):
            continue                            # drop institutional-heavy advisers
        out.append(r)
    return out


def priority_score(row: dict) -> int:
    """Rank candidates by family-office likelihood so the scheduled climb verifies
    the highest-yield firms first (a random slice is ~0% FO; FO-named ~47%)."""
    name = _name(row)
    score = 0
    if _FO_NAME.search(name):
        score += 100                       # explicit FO/multi-family name signal
    elif "family" in name.lower():
        score += 40                        # weaker family signal
    # more HNW individual clients = more likely a real family shop
    score += min(int(_num(row, "5D(b)(1)")), 30)
    return score


def candidate_from_row(row: dict) -> CandidateFirm:
    """Map an ADV roster row to a CandidateFirm. Existence + reachability only —
    NOT function (that is S10's job)."""
    name = (row.get("Primary Business Name") or row.get("Legal Name") or "").strip()
    firm = CandidateFirm(firm_name=name,
                         discovery_source="SEC Form ADV (registered adviser roster)")

    site = _real_site(row)
    if site:
        p = urlparse(site)
        firm.website = f"{p.scheme}://{p.netloc}"

    city = (row.get("Main Office City") or "").strip()
    state = (row.get("Main Office State") or "").strip()
    firm.hq_location = ", ".join(x for x in (city, state) if x) or None
    firm.cik = (row.get("CIK#") or "").strip() or None

    crd = (row.get("Organization CRD#") or "").strip()
    filed = (row.get("Latest ADV Filing Date") or "").strip()
    firm.proof_exists = (f"SEC-registered investment adviser (CRD {crd}"
                         f"{', CIK ' + firm.cik if firm.cik else ''}); "
                         f"Form ADV filed {filed}")

    phone = (row.get("Main Office Telephone Number") or "").strip()
    if phone:
        # The firm's own Form ADV main-office line — authoritative, but firm-level.
        firm.principal_phone = Cell(
            value=phone, source=f"SEC Form ADV (CRD {crd})",
            method="main-office telephone from the firm's own Form ADV",
            epistemic=Epistemic.FACT, confidence=Confidence.HIGH)

    # Own-filing context (not function proof): the firm reports HNW-individual
    # clients on its own ADV. Recorded as background, never as Proof B.
    firm.background = Cell(
        value="Reports high-net-worth individual clients on its own Form ADV "
              "(Item 5.D(b)).",
        source=f"SEC Form ADV (CRD {crd})", method="Form ADV Item 5.D",
        epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)
    return firm


@register
class SECFormADV(DiscoverySource):
    name = "SEC Form ADV (registered adviser roster)"
    job = "discovery (registered advisers with own website — MFO/FO candidates)"

    def _load_rows(self) -> List[dict]:
        if os.path.exists(CACHE):
            with open(CACHE, encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f))
        url = self._latest_zip_url()
        raw = self.get(url).content
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            csv_name = z.namelist()[0]
            text = z.read(csv_name).decode("latin-1")
        rows = list(csv.DictReader(io.StringIO(text)))
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8", newline="") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        return rows

    def _latest_zip_url(self) -> str:
        import re
        html = self.get(DATA_PAGE).text
        # hrefs look like /files/.../ia050126.zip ; pick the newest by MMDDYY.
        links = re.findall(r'href="([^"]*?ia(\d{2})(\d{2})(\d{2})\.zip)"', html)
        if not links:
            raise RuntimeError("no ADV roster ZIP link found on the SEC data page")
        # sort key = (YY, MM, DD)
        best = max(links, key=lambda m: (m[3], m[1], m[2]))
        href = best[0]
        return href if href.startswith("http") else "https://www.sec.gov" + href

    def discover(self, limit: int = 8000) -> List[CandidateFirm]:
        try:
            rows = self._load_rows()
        except Exception as e:
            print(f"[{self.name}] roster load error: {e}")
            return []
        # WIDE net: every HNW-serving adviser with a site + every FO-named firm
        # (institutional allowed). Proof B still gates quality, so a wider net only
        # extends the runway; priority_score verifies the likeliest FOs first.
        picked = select_rows(rows, concentrated=False, name_net=True)
        picked.sort(key=priority_score, reverse=True)   # FO-signal candidates first
        return [candidate_from_row(r) for r in picked[:limit]]
