"""Escalation detection — the climb parks genuinely ambiguous records for a human.

The queue itself (rag/escalation.py: open_case / pending_cases / resolve_case,
with the human-authorization log) existed but nothing in the pipeline ever called
it — needs_human.json had never seen a real case. This module is the missing
caller. Two conflicts the pipeline must NOT decide:

1. Conflicting type evidence: the own-source type quote carries BOTH single- and
   multi-family markers, or an SEC family-office exemption (single-family by
   definition) coexists with an own-site multi-family statement.
2. Entity mismatch on a proven firm: FO-function proven from the firm's own
   site, but whole-record entity resolution failed.

A conflicted record is set to record_status "Review" (only Qualified ships on a
customer surface) and one case per firm key is opened in needs_human.json with
the evidence. The pipeline never resolves a case — resolve_case() is the
human's; a firm whose case a human already handled is not re-parked.
"""
from __future__ import annotations

from typing import Optional

from pipeline.schema import CandidateFirm
from pipeline.validation.relabel import _MULTI, _SINGLE
from rag.escalation import NEEDS_HUMAN, LOG, _load, open_case


def type_conflict(firm: CandidateFirm) -> Optional[str]:
    tq = (firm.proof_type_quote or "").lower()
    multi = any(m in tq for m in _MULTI)
    single = any(s in tq for s in _SINGLE)
    if multi and single:
        return ("conflicting type evidence: own-source type quote contains both "
                f"single- and multi-family markers: \"{firm.proof_type_quote}\"")
    if bool(firm.sec_family_office_exemption) and multi:
        return ("conflicting type evidence: SEC family-office exemption "
                "(single-family by definition) but the firm's own site states "
                f"multi-family: \"{firm.proof_type_quote}\"")
    return None


def entity_conflict(firm: CandidateFirm) -> Optional[str]:
    if firm.proof_function_quote and firm.entity_coherent is False:
        return ("entity mismatch: FO-function proven from the firm's own site, "
                "but whole-record entity resolution failed (cross-entity values "
                "quarantined) — identity needs a human call")
    return None


def escalate_ambiguous(firms, path: str = NEEDS_HUMAN, log: str = LOG) -> int:
    """Detect conflicts, park each record as Review, open one case per firm key.
    A firm with a case already in the queue (pending OR human-resolved) is not
    re-opened; pending ones stay parked. Returns records parked this run."""
    from pipeline.state import firm_key
    known = {c.get("context", {}).get("firm_key") for c in _load(path)}
    parked = 0
    for f in firms:
        reason = type_conflict(f) or entity_conflict(f)
        if not reason:
            continue
        k = firm_key(f)
        if k in known:
            resolved = any(c.get("context", {}).get("firm_key") == k
                           and c["status"] != "pending" for c in _load(path))
            if resolved:
                continue                  # human already ruled; don't re-park
            f.record_status = "Review"    # case still pending -> stays parked
            parked += 1
            continue
        f.record_status = "Review"        # the pipeline does not decide this one
        f.rejection_reason = None
        parked += 1
        open_case(reason, context={
            "firm_key": k,
            "firm_name": f.firm_name,
            "proof_function_quote": f.proof_function_quote,
            "proof_type_quote": f.proof_type_quote,
            "sec_family_office_exemption": f.sec_family_office_exemption,
            "entity_coherent": f.entity_coherent,
            "website": f.website,
            "discovery_source": f.discovery_source,
        }, options=(["SFO", "MFO", "FO-type-unknown", "Reject"]
                    if type_conflict(f) else
                    ["confirm identity + qualify", "reject record"]),
            path=path, log=log)
        known.add(k)
    return parked
