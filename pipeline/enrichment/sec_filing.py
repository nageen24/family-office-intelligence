"""Filing-based enrichment from SEC EDGAR (free, no key, official).

For any firm discovered with a CIK, SEC's submissions JSON gives the entity's
official business address and phone straight from its filings. This is the
honest answer to the "no website" case (see DECISIONS.md): a real, source-backed
phone/address even when the firm has no site — never a guessed contact.

A phone/address that comes from an SEC filing is treated as FACT / high
confidence: it's an official self-reported record, not scraped guesswork.
"""
from __future__ import annotations

from typing import Optional

from pipeline.discovery.base import DiscoverySource
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

_http = DiscoverySource()  # reuse polite session + required UA


def _fmt_addr(b: dict) -> Optional[str]:
    parts = [b.get("street1"), b.get("street2"), b.get("city"),
             b.get("stateOrCountry"), b.get("zipCode")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def enrich_from_sec(firm: CandidateFirm) -> CandidateFirm:
    if not firm.cik:
        return firm
    try:
        data = _http.get(SUBMISSIONS.format(cik=firm.cik)).json()
    except Exception as e:
        print(f"[sec_filing] {firm.firm_name} (CIK {firm.cik}): {e}")
        return firm

    asof = None
    filings = (data.get("filings", {}) or {}).get("recent", {}) or {}
    dates = filings.get("filingDate") or []
    if dates:
        asof = dates[0]  # most recent filing date = as-of for the record

    # official business phone
    phone = (data.get("phone") or "").strip()
    if phone and firm.principal_phone.is_blank():
        firm.principal_phone = Cell(
            value=phone, source=f"SEC EDGAR submissions CIK {firm.cik}",
            method="official SEC filing (business phone)",
            epistemic=Epistemic.FACT, confidence=Confidence.HIGH, asof_date=asof,
        )

    # official business address -> hq_location (prefer the filed one)
    addr = _fmt_addr((data.get("addresses", {}) or {}).get("business", {}) or {})
    if addr:
        firm.hq_location = addr

    # short factual background from the filing entity record
    sic = (data.get("sicDescription") or "").strip()
    if sic and firm.background.is_blank():
        firm.background = Cell(
            value=f"SEC-registered filer; industry: {sic}.",
            source=f"SEC EDGAR submissions CIK {firm.cik}",
            method="SEC entity record", epistemic=Epistemic.FACT,
            confidence=Confidence.HIGH, asof_date=asof,
        )
    return firm
