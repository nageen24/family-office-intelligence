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
# RULE 2 (strict, per the assessment): a firm does NOT qualify merely because
# its name contains family-office words, it serves wealthy clients, or it
# appeared in an FO-associated source. We require AFFIRMATIVE evidence from an
# independent basis: an official filing under an FO name, or FO self-description
# / press description in gathered text. Name alone => Unconfirmed => Rejected.
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


# Press-possessive SFO rule (candidate's written standard, see PROOF_STANDARD.md):
# a headline attributing the office to ONE named individual ("Jeff Bezos' family
# office", "the family office of Ray Dalio") is affirmative single-family
# evidence — an office belonging to one named person serves one family by
# definition. Inference/medium, evidence = the exact headline; fires ONLY on a
# person-name possessive, never on generic names ("Singapore Family Office").
_PERSON = r"[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+){1,2}?"
_POSSESSIVE_SFO = [
    re.compile(rf"({_PERSON})['’‘`]s?\s+[Ff]amily\s+[Oo]ffice"),
    re.compile(rf"[Ff]amily\s+[Oo]ffice\s+of\s+({_PERSON})\b"),
]


# words that prove the "person" match is actually a company/place, not a human
_NOT_A_PERSON = {"inc", "llc", "lp", "ltd", "corp", "co", "group", "capital",
                 "partners", "holdings", "america", "global", "management",
                 "investments", "ventures", "advisors", "trust", "firm"}


def _is_person(name: str) -> bool:
    words = name.split()
    return (2 <= len(words) <= 3
            and not any(w.lower().strip(".,") in _NOT_A_PERSON for w in words))


def _possessive_sfo_evidence(firm: CandidateFirm) -> str | None:
    # Basis 1: the firm's recent-signal headline carries a person-possessive.
    sig = firm.recent_signal
    if not sig.is_blank():
        for pat in _POSSESSIVE_SFO:
            m = pat.search(sig.value or "")
            if m and _is_person(m.group(1).strip()):
                return (f"press attributes office to one individual "
                        f"('{m.group(1).strip()}') — headline: "
                        f"\"{(sig.value or '')[:120]}\" [{sig.source}] "
                        f"(inference/medium)")
    # Basis 2: enrichment already extracted a principal FROM a possessive/hire
    # headline (news_signal.py) — same evidence, stored with its source URL.
    pn = firm.principal_name
    if (not pn.is_blank() and pn.method and "headline" in pn.method
            and _is_person(pn.value or "")):
        return (f"press names one individual behind the office "
                f"('{pn.value}') [{pn.source}] (inference/medium)")
    return None


def classify_firm(firm: CandidateFirm) -> Tuple[FirmType, str]:
    """Return (type, evidence). Evidence must be independent of the name."""
    name_l = (firm.firm_name or "").lower()
    name_says_fo = "family office" in name_l
    # A firm that calls ITSELF multi-family is affirmative MFO evidence — and it
    # must never fall through to an SFO label (caught: "Covenant Multifamily
    # Offices" was tagged SFO). This name signal is self-description, not a
    # bare family-office word, so it's legitimate Rule-2 evidence.
    if ("multifamily" in name_l or "multi-family" in name_l
            or "multi family" in name_l):
        return FirmType.MFO, f"firm's own name states multi-family: '{firm.firm_name}'"

    # Text gathered ABOUT the firm (site copy, filing record, news headline) —
    # deliberately excludes the firm's own name, which proves nothing.
    blob = " ".join([
        firm.background.value or "",
        firm.investing_thesis.value or "",
        firm.mandate.value or "",
        firm.recent_signal.value or "",
    ]).lower()

    # Strongest basis: an official SEC filing made under a family-office name
    # (13F/EDGAR — set by enrichment into type_evidence). FOs are ADV-exempt
    # but not 13F-exempt, so this is affirmative federal evidence.
    filed_as_fo = bool(firm.type_evidence and "13F" in firm.type_evidence)

    sfo_hits = [m for m in SFO_MARKERS if m in blob]
    mfo_hits = [m for m in MFO_MARKERS if m in blob]
    press_fo = "family office" in blob  # independent text calls it an FO

    if mfo_hits:
        return FirmType.MFO, f"MFO evidence in gathered text: {mfo_hits}"
    if sfo_hits:
        return FirmType.SFO, f"SFO evidence in gathered text: {sfo_hits}"
    poss = _possessive_sfo_evidence(firm)
    if poss:
        return FirmType.SFO, poss
    if filed_as_fo:
        # A 13F filing under a family-office name proves it's a REAL, ACTIVE
        # family office — but NOT that it serves one family. Many multi-family
        # offices (Pathstone, Callan, Colony, Geller) also file 13F under a
        # "Family Office" name. Calling these SFO on 13F alone is exactly the
        # "most serious error" the assessment names. So: Unconfirmed, honestly,
        # unless single-family evidence appears above. (Corrected after review.)
        return FirmType.UNCONFIRMED, (
            firm.type_evidence + "; single- vs multi-family unproven")

    # SEC-registered OPERATING entity under a family-office name. This is name
    # PLUS federal registration (a CIK), SEC filings, and a verified business
    # address/phone from those filings — materially more than "name alone", so
    # it clears Rule 2 as a real family office. We do NOT claim single vs multi
    # here (that stays Unconfirmed unless proven), except that a bank/wirehouse-
    # affiliated FO is by nature multi-family. (Candidate decision, logged.)
    sec_operating = bool(firm.cik and (not firm.principal_phone.is_blank()
                                       or firm.hq_location))
    if sec_operating and name_says_fo:
        banks = ("bmo", "ubs", "deutsche", "morgan", "goldman", "northern trust",
                 "citi", "hsbc", "wells fargo", "bny", "jpmorgan", "j.p. morgan")
        if any(b in name_l for b in banks):
            return FirmType.MFO, (
                f"bank/wirehouse-affiliated SEC-registered family office "
                f"(CIK {firm.cik}, verified filing address/phone)")
        return FirmType.UNCONFIRMED, (
            f"SEC-registered operating entity (CIK {firm.cik}) with verified "
            f"filing address/phone; single- vs multi-family split unproven")

    if press_fo and name_says_fo:
        # Independent press/filing text describes it as a family office.
        return FirmType.UNCONFIRMED, (
            "described as family office in gathered text; SFO/MFO split unproven")
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

        # EXISTENCE GATE (before any type label matters): a firm must be
        # provable as a real entity — an SEC CIK, a resolved website, a
        # registry/990 location, or a named principal. A name that exists only
        # inside one headline fragment is a phantom, and phantom "SFOs" are
        # the worst records a file can carry ("Revised Single Family Office"
        # was headline debris that self-certified via its own name — caught in
        # testing, hence this gate).
        exists = bool(firm.cik or firm.website or firm.hq_location
                      or not firm.principal_name.is_blank())
        if not exists:
            firm.record_status = "Rejected"
            firm.rejection_reason = ("existence unproven: no SEC entity, website, "
                                     "registry location, or named principal")
            continue

        # Qualification decision (Rule 2 is the gate, thinness second).
        # Distinction the assessment draws: a firm whose FO-ness we cannot
        # establish does NOT qualify; a proven FO whose SFO/MFO split is
        # unclear may qualify with the type stated honestly as Unconfirmed.
        if ftype == FirmType.UNCONFIRMED and "no affirmative" in evidence:
            firm.record_status = "Rejected"
            firm.rejection_reason = "Rule 2: no affirmative family-office evidence"
        elif firm.reachability_score < min_score and firm.background.is_blank():
            firm.record_status = "Rejected"
            firm.rejection_reason = "too thin: no contactability and no supporting detail"
        else:
            firm.record_status = "Qualified"
    return pool
