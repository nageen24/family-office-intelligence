"""Apply browser-sourced, verified websites + emails into the candidate pool.

Provenance is stated honestly: websites were discovered by automated Bing
queries run through a REAL browser (every scripted search engine IP-blocks this
environment — see DECISIONS.md), then each candidate was verified by a direct
fetch confirming the firm's own name + family-office context on the page. Emails
were scraped only from those verified, same-domain pages. This is automated
enrichment routed through the browser as transport — not hand-compiled records.

Findings still govern release: emails flow into validation's MX/deliverability
check, and a failure there removes the email from the delivered record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence

VERIFIED = Path("data/interim/web_verified.json")
TODAY = "2026-07-28"


def apply_web(pool: List[CandidateFirm]) -> List[CandidateFirm]:
    if not VERIFIED.exists():
        return pool
    data = json.loads(VERIFIED.read_text(encoding="utf-8"))
    by_name = {f.firm_name: f for f in pool}
    applied_w = applied_e = 0
    for name, rec in data.items():
        firm = by_name.get(name)
        if not firm:
            continue
        w = rec.get("website")
        if w and not firm.website:
            firm.website = w
            applied_w += 1
        email = rec.get("email")
        if email and firm.principal_email.is_blank():
            firm.principal_email = Cell(
                value=email, source=w,
                method="scraped from firm site (Bing-found, name-verified); "
                       "MX-checked in validation",
                epistemic=Epistemic.INFERENCE, confidence=Confidence.LOW,
                asof_date=TODAY)
            applied_e += 1
    print(f"[apply_web] websites +{applied_w}, emails +{applied_e}")
    return pool
