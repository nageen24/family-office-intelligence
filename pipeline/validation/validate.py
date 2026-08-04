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

from pipeline.schema import (CandidateFirm, Cell, Confidence, Epistemic)
from pipeline.ontology import (Status, email_status, counts_toward_500,
                               meets_inclusion_floor, meets_commercial_standard)
from pipeline.validation.entity import resolve_entity
from pipeline.validation.relabel import relabel_record

TODAY = date.today().isoformat()


# --- email verification ---------------------------------------------------------
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$")


def _dns_mx(domain: str) -> bool:
    try:
        return len(dns.resolver.resolve(domain, "MX")) > 0
    except Exception:
        return False


def smtp_probe(email: str, timeout: int = 8) -> str:
    """Free mailbox check via SMTP RCPT, with catch-all detection.

    Returns one of: 'deliverable' (RCPT for the address accepted AND a random
    address on the same domain is rejected), 'catch_all' (both accepted — the
    server accepts everything, so nothing is proven), 'undeliverable' (address
    rejected), 'unknown' (port 25 blocked / timeout / greylisted — common for
    Microsoft-365 domains; we do NOT claim verified on an inconclusive probe).
    """
    import smtplib
    import uuid
    domain = email.split("@", 1)[1]
    try:
        mx = sorted((r.preference, str(r.exchange).rstrip("."))
                    for r in dns.resolver.resolve(domain, "MX"))[0][1]
    except Exception:
        return "unknown"
    try:
        s = smtplib.SMTP(timeout=timeout)
        s.connect(mx, 25)
        s.helo("example.com")
        s.mail("verify@example.com")
        code, _ = s.rcpt(email)
        rnd, _ = s.rcpt(f"{uuid.uuid4().hex}@{domain}")
        s.quit()
    except Exception:
        return "unknown"
    if code in (250, 251):
        return "catch_all" if rnd in (250, 251) else "deliverable"
    if code in (550, 551, 553, 554):
        return "undeliverable"
    return "unknown"


def verify_email(cell: Cell, mx_lookup=_dns_mx, probe=smtp_probe) -> Cell:
    """MX + free SMTP mailbox check, mapped to the S2 status vocab.

    verified = the mailbox itself was confirmed (SMTP RCPT deliverable on a
    non-catch-all domain). MX-only, catch-all, or an inconclusive/blocked probe =
    inferred. A failed check (bad syntax, no MX, undeliverable) is QUARANTINED —
    withheld from the customer surface, original kept in the cell's audit fields.
    Both the MX lookup and the SMTP probe are injectable for testing.
    """
    if cell.status is Status.QUARANTINED:
        return cell            # already withheld (e.g. cross-entity) — don't revive
    if cell.is_blank():
        return cell.mark_unresolved()
    m = EMAIL_RE.match(cell.value.strip())
    if not m:
        return cell.quarantine("invalid email syntax")
    domain = m.group(1)
    if not mx_lookup(domain):
        return cell.quarantine(f"no MX record for {domain} (undeliverable)")

    result = probe(cell.value.strip())
    if result == "undeliverable":
        return cell.quarantine("SMTP RCPT rejected the mailbox (undeliverable)")

    st = email_status(has_syntax=True, has_mx=True,
                      mailbox_confirmed=(result == "deliverable"),
                      catch_all=(result == "catch_all"))
    cell.status = st
    if st == Status.VERIFIED:
        cell.confidence = Confidence.HIGH
        cell.epistemic = Epistemic.FACT
        cell.method = "SMTP RCPT: mailbox confirmed deliverable"
    else:  # INFERRED
        cell.confidence = Confidence.MEDIUM
        cell.epistemic = Epistemic.INFERENCE
        cell.method = ("MX present; mailbox unconfirmed "
                       f"(SMTP probe: {result})")
    cell.asof_date = TODAY
    return cell


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


def _beyond_seed_count(firm: CandidateFirm) -> int:
    """Non-blank, non-quarantined cells obtained BEYOND the discovery source.

    The own-site function proof (Proof B) is beyond-seed by construction; so are
    principal/contact/thesis/signal cells captured during enrichment. Cells that
    merely echo the discovery seed (the ADV background note) do not count.
    """
    n = 0
    if firm.proof_function_source and firm.proof_function_source == firm.website:
        n += 1
    for name in ("principal_name", "principal_title", "principal_email",
                 "recent_signal", "investing_thesis", "mandate"):
        c = getattr(firm, name)
        if not c.is_blank() and c.status is not Status.QUARANTINED:
            n += 1
    return n


# --- orchestrated validation ----------------------------------------------------
def validate_all(pool: List[CandidateFirm], min_score: int = 20) -> List[CandidateFirm]:
    for firm in pool:
        # S6: resolve the whole record to ONE entity — quarantine cross-entity
        # values (snow-crab signals, foreign-domain emails) and set entity_coherent.
        resolve_entity(firm)

        # Rule 1: verify high-value cells; findings govern release.
        firm.principal_email = verify_email(firm.principal_email)

        # S7: relabel to the narrowest labels — strict 5-category classification
        # (Proof B = own filing/exemption only), contact routes, per-cell status.
        relabel_record(firm)

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

        # S3 inclusion floor: a record counts only as a qualifying category with
        # proven existence + FO-function + entity coherence + >=1 beyond-seed cell.
        function_proven = bool(firm.proof_function_quote or firm.sec_family_office_exemption)
        firm.counts_toward_500 = meets_inclusion_floor(
            firm.category, exists=exists, function_proven=function_proven,
            entity_coherent=bool(firm.entity_coherent),
            beyond_seed_cells=_beyond_seed_count(firm))

        # S3 commercial standard (the worth-buying tier; a flag, not a gate).
        firm.is_commercial = meets_commercial_standard(
            has_decision_maker=not firm.principal_name.is_blank(),
            has_focus_or_mandate=(not firm.investing_thesis.is_blank()
                                  or not firm.mandate.is_blank()),
            has_reachable_route=(not firm.principal_email.is_blank()
                                 or not firm.principal_phone.is_blank()),
            has_dated_signal=(not firm.recent_signal.is_blank()
                              and bool(firm.recent_signal.asof_date)))

        if firm.counts_toward_500:
            firm.record_status = "Qualified"
        else:
            firm.record_status = "Rejected"
            firm.rejection_reason = (
                f"{firm.category.value}: does not meet the inclusion floor "
                f"({firm.type_evidence})")
    return pool
