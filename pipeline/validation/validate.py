"""Validation engine — the accuracy core of the dataset.

Two separate rules (see DECISIONS.md / PROOF_STANDARD.md):

RULE 2 (firm): a record qualifies ONLY with affirmative evidence the firm is a
family office. We classify SFO / MFO / Unconfirmed from evidence markers and
record the exact `type_evidence`. We never upgrade to SFO to inflate value.

RULE 1 (cells): every high-value cell carries source + method + confidence +
epistemic + as-of. Emails get an MX + (optional) deliverability check; a value
that FAILS is removed from the customer field and the failure is logged
(findings govern release). Honest blank over fake, always.

Firms that fail Rule 2, or have no supportable value at all, are marked
Rejected with a reason and routed to the rejection log — not deleted, so the
validation is provably output-changing, not just measurement.
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import List, Tuple

import dns.resolver

from pipeline.schema import (CandidateFirm, Cell, FirmType, Confidence, Epistemic)

TODAY = date.today().isoformat()

# --- firm-type evidence markers -------------------------------------------------
SFO_MARKERS = [
    "single family office", "single-family office", "our family",
    "one family", "family's capital", "we are the family office",
    "does not accept external", "not accepting new clients",
]
MFO_MARKERS = [
    "multi family office", "multi-family office", "families we serve",
    "our clients", "become a client", "client login", "fee schedule",
    "wealth management services", "advisory services", "onboarding",
]
FO_MARKERS = ["family office", "wealth", "family capital", "family investment"]


def classify_firm(firm: CandidateFirm) -> Tuple[FirmType, str]:
    """Return (type, evidence) from whatever text we gathered."""
    blob = " ".join([
        firm.background.value or "",
        firm.investing_thesis.value or "",
        firm.firm_name or "",
    ]).lower()

    sfo_hits = [m for m in SFO_MARKERS if m in blob]
    mfo_hits = [m for m in MFO_MARKERS if m in blob]
    fo_hits = [m for m in FO_MARKERS if m in blob]

    if sfo_hits and not mfo_hits:
        return FirmType.SFO, f"SFO markers: {sfo_hits}"
    if mfo_hits:
        return FirmType.MFO, f"MFO markers: {mfo_hits}"
    if fo_hits:
        # Looks like an FO but type is genuinely unclear — say so (allowed).
        return FirmType.UNCONFIRMED, f"FO language but type unclear: {fo_hits}"
    return FirmType.UNCONFIRMED, "no affirmative family-office evidence found"


# --- email verification ---------------------------------------------------------
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$")


def verify_email(cell: Cell) -> Cell:
    """MX check (free) + optional Hunter free tier. Findings govern release."""
    if cell.is_blank():
        return cell
    m = EMAIL_RE.match(cell.value.strip())
    if not m:
        return _blank(cell, "invalid email syntax")
    domain = m.group(1)
    try:
        answers = dns.resolver.resolve(domain, "MX")
        has_mx = len(answers) > 0
    except Exception:
        has_mx = False
    if not has_mx:
        # No mail server for the domain -> undeliverable -> remove from field.
        return _blank(cell, f"no MX record for {domain} (undeliverable)")

    # Optional stronger check if a Hunter key is present.
    hunter_key = os.getenv("HUNTER_API_KEY")
    if hunter_key:
        try:
            import requests
            r = requests.get("https://api.hunter.io/v2/email-verifier",
                             params={"email": cell.value, "api_key": hunter_key},
                             timeout=20)
            status = r.json().get("data", {}).get("status")
            if status in ("undeliverable", "invalid"):
                return _blank(cell, f"Hunter: {status}")
            cell.method = f"MX ok + Hunter:{status}"
            cell.confidence = Confidence.HIGH if status == "deliverable" else Confidence.MEDIUM
            cell.epistemic = Epistemic.FACT
            cell.asof_date = TODAY
            return cell
        except Exception:
            pass

    cell.method = "MX record present (domain accepts mail)"
    cell.confidence = Confidence.MEDIUM  # MX alone can't confirm the mailbox
    cell.epistemic = Epistemic.INFERENCE
    cell.asof_date = TODAY
    return cell


def _blank(cell: Cell, reason: str) -> Cell:
    """Turn a failed cell into an honest blank, preserving the reason as method."""
    return Cell(value=None, source=cell.source,
                method=f"could not verify — {reason}",
                confidence=None, epistemic=None, asof_date=TODAY)


# --- reachability score (dual-factor: contactability AND freshness) -------------
def reachability(firm: CandidateFirm) -> int:
    score = 0
    if not firm.principal_email.is_blank():
        score += 30
    if not firm.principal_phone.is_blank():
        score += 25
    if not firm.principal_linkedin.is_blank() or firm.corporate_linkedin:
        score += 10
    if not firm.principal_name.is_blank():
        score += 10
    # freshness: a dated recent signal
    if not firm.recent_signal.is_blank() and firm.recent_signal.asof_date:
        score += 25
    return min(score, 100)


# --- orchestrated validation ----------------------------------------------------
def validate_all(pool: List[CandidateFirm], min_score: int = 20) -> List[CandidateFirm]:
    for firm in pool:
        # Rule 2 first: what is this firm?
        ftype, evidence = classify_firm(firm)
        firm.firm_type = ftype
        firm.type_evidence = evidence

        # Rule 1: verify high-value cells; findings govern release.
        firm.principal_email = verify_email(firm.principal_email)

        firm.reachability_score = reachability(firm)

        # Qualification decision.
        if ftype == FirmType.UNCONFIRMED and "no affirmative" in evidence:
            firm.record_status = "Rejected"
            firm.rejection_reason = "Rule 2: no affirmative family-office evidence"
        elif firm.reachability_score < min_score and firm.background.is_blank():
            firm.record_status = "Rejected"
            firm.rejection_reason = "too thin: no contactability and no supporting detail"
        else:
            firm.record_status = "Qualified"
    return pool
