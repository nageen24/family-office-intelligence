"""S7 — relabel every value to its narrowest accurate label.

Firm level (classify_category): the 5-category ontology under STRICT Proof B.
Function is proven ONLY by the firm's own site/filing/document stating it
operates as a family office, or a SEC family-office exemption. A firm known only
by name, a 13F filing, press, or a registry class does NOT clear Proof B and is
Unresolved-Quarantine (fix#3). Type (Proof C) is read from an own-source quote.

Cell level (narrow_status): the S2 status word. Authoritative primary source =
verified; derived/indirect = inferred; blank = unresolved; a failed or
cross-entity value stays quarantined (never revived). Contact cells get a route.
"""
from __future__ import annotations

import re

from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.ontology import FirmCategory, Status, RouteType, email_route

_MULTI = ("multi-family", "multi family", "multifamily", "multiple families",
          "families we serve", "our clients", "each client")
_SINGLE = ("single family office", "single-family office", "one family",
           "our family", "the family we serve", "sole family")


def classify_category(firm: CandidateFirm) -> tuple[FirmCategory, str]:
    """Return (category, reason) under the strict Proof B decision."""
    exemption = bool(getattr(firm, "sec_family_office_exemption", None))
    function_proven = bool(firm.proof_function_quote) or exemption

    if not function_proven:
        if getattr(firm, "ria_adviser_evidence", None):
            return (FirmCategory.RIA_NONQUALIFYING,
                    f"affirmative general-adviser evidence, no FO-function proof: "
                    f"{firm.ria_adviser_evidence}")
        return (FirmCategory.UNRESOLVED_QUARANTINE,
                "FO-function not proven from the firm's own site/filing/exemption "
                "(name / 13F / press / registry do not prove function)")

    # Function is proven — now the single-vs-multi split (Proof C).
    if exemption:
        return (FirmCategory.SFO,
                "SEC family-office exemption (single-family by definition)")
    tq = (firm.proof_type_quote or "").lower()
    if any(m in tq for m in _MULTI):
        return (FirmCategory.MFO, f"own-source multi-family statement: \"{firm.proof_type_quote}\"")
    if any(s in tq for s in _SINGLE):
        return (FirmCategory.SFO, f"own-source single-family statement: \"{firm.proof_type_quote}\"")
    return (FirmCategory.FO_TYPE_UNKNOWN,
            f"FO-function proven (\"{firm.proof_function_quote}\"); single- vs "
            f"multi-family unproven")


def narrow_status(cell: Cell, derived: bool = False) -> Cell:
    """Assign the narrowest S2 status word to a value.

    verified   -> stated by an authoritative primary source (epistemic FACT) and
                  not a derived/computed figure.
    inferred   -> derived/computed, or indirect/reasoned evidence.
    unresolved -> blank (never found).
    quarantined-> a failed check / cross-entity value is left untouched.
    """
    if cell.status is Status.QUARANTINED:
        return cell
    if cell.is_blank():
        return cell.mark_unresolved()
    if derived:
        cell.status = Status.INFERRED
    else:
        cell.status = (Status.VERIFIED if cell.epistemic is Epistemic.FACT
                       else Status.INFERRED)
    return cell


_PERSONAL_PHONE = re.compile(r"\b(direct|mobile|cell|personal)\b", re.I)


def phone_route(cell: Cell) -> RouteType:
    """A phone is personal only when its source calls it a direct/mobile line; a
    main/switchboard/SEC-filing number is firm-level (fix#6)."""
    if cell.is_blank():
        return RouteType.FIRM_LEVEL
    hay = f"{cell.method or ''} {cell.source or ''}"
    return RouteType.PERSONAL if _PERSONAL_PHONE.search(hay) else RouteType.FIRM_LEVEL


def _category_to_firmtype(cat: FirmCategory):
    from pipeline.schema import FirmType
    if cat is FirmCategory.SFO:
        return FirmType.SFO
    if cat is FirmCategory.MFO:
        return FirmType.MFO
    return FirmType.UNCONFIRMED


# Cells narrowed generically; email owns its own status via verify_email.
_FACT_CELLS = ["investing_thesis", "mandate", "background", "principal_name",
               "principal_title", "principal_linkedin", "principal_phone",
               "recent_signal"]


def relabel_record(firm: CandidateFirm) -> CandidateFirm:
    """Apply the narrowest firm category, contact routes, and cell status words."""
    cat, reason = classify_category(firm)
    firm.category = cat
    firm.firm_type = _category_to_firmtype(cat)   # back-compat mirror
    firm.type_evidence = reason

    # routes on the two contact cells
    if not firm.principal_email.is_blank():
        firm.principal_email.route = email_route(
            firm.principal_email.value, firm.principal_name.value or "")
    firm.principal_phone.route = phone_route(firm.principal_phone)

    # AUM is a computed/derived figure (13F portfolio value) -> never verified.
    narrow_status(firm.aum, derived=True)
    for name in _FACT_CELLS:
        narrow_status(getattr(firm, name))
    return firm
