"""13F-based enrichment: principal signature + portfolio value (keyless, official).

WHY THIS MATTERS (the SFO insight — see DECISIONS.md):
Family offices are exempt from SEC *adviser* registration (the Family Office
Rule), which is why the best SFOs are invisible to Form ADV. But NOTHING
exempts them from Form 13F: any institution holding >$100M in US-listed
equities must file. So a 13F filer whose name says "Family Office" is a
REAL, provably active family office — official Rule-2 evidence plus the
highest-value records in the file (Duquesne, Soros-class firms live here).

What the 13F primary_doc.xml gives us, all official:
- signature block: signer NAME + TITLE + PHONE  (decision-maker intel)
- tableValueTotal: total 13F portfolio value     (an AUM-class figure)
- periodOfReport / filing date                    (freshness)

The value is stated in THOUSANDS of USD in modern filings; we convert and
label it "13F portfolio value" — honestly NOT total AUM (real AUM >= 13F
value since it excludes bonds, private deals, cash, non-US assets). The cell
says exactly what it is; overstating it as full AUM would be a fake.
"""
from __future__ import annotations

import re
from typing import Optional

from pipeline.discovery.base import DiscoverySource
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}"

_http = DiscoverySource()  # polite session with required SEC UA


def _tag(xml: str, tag: str) -> Optional[str]:
    m = re.search(rf"<(?:\w+:)?{tag}>(.*?)</(?:\w+:)?{tag}>", xml, re.S | re.I)
    return m.group(1).strip() if m else None


def _fmt_value_thousands(raw: str, entries: Optional[str] = None) -> Optional[str]:
    """tableValueTotal: thousands in older filings, full dollars in newer ones —
    and filers are inconsistent about which they use, even in the same year.

    Disambiguation uses two signals, and reads as dollars if EITHER fires:
      (a) raw >= $100M — a firm only files 13F if it holds >=$100M, so a raw
          already at/above 100,000,000 is dollars (as thousands it'd be >=$100B).
      (b) raw*1000 / holdings > $100M average position — an average single 13F
          holding above $100M is implausible, so the total must already be dollars.
    Otherwise it's thousands and we multiply by 1,000.

    This keeps Duquesne (raw 3,380,000, 70 holdings -> thousands -> $3.38B; avg
    $48M) correct, while fixing dollar-reporting filers the old heuristic inflated
    1000x: CVA (949,646,263 -> $949.6M), Fortitude ($516.0M), Standard (96,780,000,
    31 holdings; avg-if-thousands $3.1B -> dollars -> $96.78M). Zero/garbage ->
    None (an honest blank beats a fake $0).
    """
    try:
        n = int(raw.replace(",", "").split(".")[0])
    except (ValueError, AttributeError):
        return None
    if n <= 0:
        return None
    try:
        e = int(entries) if entries else 0
    except (ValueError, TypeError):
        e = 0

    is_dollars = n >= 100_000_000 or (e > 0 and (n * 1000) / e > 100_000_000)
    v = n if is_dollars else n * 1000

    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B (13F portfolio value)"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M (13F portfolio value)"
    return f"${v:,} (13F portfolio value)"


def enrich_from_13f(firm: CandidateFirm) -> CandidateFirm:
    """Fill principal name/title/phone + AUM-class value from the latest 13F."""
    if not firm.cik:
        return firm
    try:
        sub = _http.get(SUBMISSIONS.format(cik=firm.cik)).json()
    except Exception as e:
        print(f"[13f] {firm.firm_name}: submissions fetch failed: {e}")
        return firm

    rec = (sub.get("filings", {}) or {}).get("recent", {}) or {}
    forms = rec.get("form") or []
    idx = next((i for i, f in enumerate(forms) if f.startswith("13F-HR")), None)
    if idx is None:
        return firm  # not a 13F filer — nothing to claim, no guess

    acc = (rec.get("accessionNumber") or [])[idx].replace("-", "")
    fdate = (rec.get("filingDate") or [])[idx]
    url = ARCHIVE.format(cik_int=int(firm.cik), acc=acc) + "/primary_doc.xml"
    try:
        xml = _http.get(url).text
    except Exception as e:
        print(f"[13f] {firm.firm_name}: primary_doc fetch failed: {e}")
        return firm

    src = f"SEC 13F-HR {fdate} (CIK {firm.cik})"

    # --- decision-maker signature block (official) ---
    # Scope to <signatureBlock> FIRST: a bare <name> search grabs the first name
    # in the doc, which is often an otherManager (AQR, FMR) from the cover page —
    # not the human signer. Reading name/title/phone from inside the signature
    # block is what recovers the real decision-maker (e.g. Biltmore -> Christopher
    # H. A. Cecil, Callan -> John Ginter) the earlier pass missed.
    sig = re.search(r"<(?:\w+:)?signatureBlock>(.*?)</(?:\w+:)?signatureBlock>",
                    xml, re.S | re.I)
    sig_xml = sig.group(1) if sig else xml
    name = _tag(sig_xml, "name")
    title = _tag(sig_xml, "title")
    phone = _tag(sig_xml, "phone")
    # The signer is sometimes the firm itself; only take a human-looking name.
    if name and firm.principal_name.is_blank():
        looks_human = (2 <= len(name.split()) <= 4
                       and name != name.upper()  # ALL-CAPS = corporate entity
                       and name.lower() not in firm.firm_name.lower()
                       and not any(w in name.lower() for w in
                                   ("llc", "lp", "inc", "corp", "office",
                                    "management", "investments", "co.", " co",
                                    "partners", "capital", "advisors", "trust")))
        if looks_human:
            firm.principal_name = Cell(
                value=name, source=url, method="13F signature block",
                epistemic=Epistemic.FACT, confidence=Confidence.HIGH,
                asof_date=fdate)
    if title and firm.principal_title.is_blank():
        firm.principal_title = Cell(
            value=title, source=url, method="13F signature block",
            epistemic=Epistemic.FACT, confidence=Confidence.HIGH,
            asof_date=fdate)
    if phone and firm.principal_phone.is_blank():
        firm.principal_phone = Cell(
            value=phone, source=url, method="13F signature block (filer contact)",
            epistemic=Epistemic.FACT, confidence=Confidence.HIGH,
            asof_date=fdate)

    # --- portfolio value (AUM-class, honestly labeled) ---
    raw = _tag(xml, "tableValueTotal")
    entries = _tag(xml, "tableEntryTotal")
    if raw and firm.aum.is_blank():
        fmt = _fmt_value_thousands(raw, entries)
        if fmt:
            firm.aum = Cell(
                value=fmt, source=url,
                method="13F tableValueTotal — US-listed equities only, not full AUM",
                epistemic=Epistemic.FACT, confidence=Confidence.HIGH,
                asof_date=fdate)

    # --- Rule-2 evidence: an institutional filer with FO name is a real FO ---
    if "family office" in firm.firm_name.lower():
        note = f"files SEC 13F-HR as '{firm.firm_name}' ({src})"
        if not firm.type_evidence:
            firm.type_evidence = note
        elif note not in firm.type_evidence:  # idempotent: no dup note on re-run
            firm.type_evidence = firm.type_evidence + "; " + note

    return firm
