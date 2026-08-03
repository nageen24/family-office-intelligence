"""Stage-2 ontology — the single source of truth for the locked S1-S3 decisions.

Every rule the customer's trust rests on lives here as executable code, not as
prose in a prompt. Discovery, enrichment, validation and the product all import
from this module so one definition governs every surface (the Stage-1 lesson: a
control matters only when it governs EVERY surface).

Locked decisions (user-authored in DECISIONS_STAGE2.md; encoded here):

S1 — entity ontology and the three separate proofs
  - Categories: SFO / MFO / FO_TYPE_UNKNOWN count toward the 500;
    RIA_NONQUALIFYING / UNRESOLVED_QUARANTINE do not.
  - Proof A (exists): CIK v own-website v registry/filing location v named principal.
  - Proof B (FO-function): the firm's OWN site/filing/document stating it operates
    as a family office, OR a SEC family-office exemption — ONLY. A name containing
    "family office", a 13F filed under an FO name, a press article, and a registry
    class do NOT prove function.
  - Proof C (SFO vs MFO): read from the same own-source meaning-quote.
  - Mechanism: the LLM quotes the exact source sentence (reads meaning); code
    verifies that quote literally exists in the source (`quote_present`).

S2 — status vocabulary and contact route types
  - verified   = a real check ran on THIS value and passed (email: mailbox-confirmed).
  - inferred   = reasoned/indirect (email: MX-only or catch-all domain).
  - unresolved = not found / could not confirm (honest blank).
  - quarantined= failed a check; the value is WITHHELD from the customer surface.
  - Route: personal (counts toward 200+) vs firm-level (does not).

S3 — the two floors
  - Inclusion floor: qualifying category + exists + FO-function + entity-coherent
    + >=1 enriched cell obtained BEYOND the discovery source.
  - Commercial standard: named decision-maker + (focus/thesis OR mandate)
    + a reachable route (personal preferred) + a current dated signal.
"""
from __future__ import annotations

import re
from enum import Enum


# --- S1: entity categories -----------------------------------------------------
class FirmCategory(str, Enum):
    SFO = "SFO"                                 # single-family office (counts)
    MFO = "MFO"                                 # multi-family office (counts)
    FO_TYPE_UNKNOWN = "FO-type-unknown"         # proven FO, split unproven (counts)
    RIA_NONQUALIFYING = "RIA-adviser (non-qualifying)"   # does NOT count
    UNRESOLVED_QUARANTINE = "Unresolved-Quarantine"      # does NOT count


# The only categories that count toward the 500.
COUNTING_CATEGORIES = frozenset(
    {FirmCategory.SFO, FirmCategory.MFO, FirmCategory.FO_TYPE_UNKNOWN}
)


def counts_toward_500(category: FirmCategory) -> bool:
    return category in COUNTING_CATEGORIES


# --- S1: quote-existence check -------------------------------------------------
# Type detection reads MEANING (an LLM quotes the exact source sentence that
# proves function/type); code proves the quote is not hallucinated by confirming
# it literally appears in the source text. Whitespace and case are normalised so
# a faithful quote is not rejected on formatting alone; nothing else is relaxed.
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def quote_present(source_text: str, quote: str) -> bool:
    q = _normalize(quote)
    if not q:
        return False
    return q in _normalize(source_text)


# --- S2: status vocabulary -----------------------------------------------------
class Status(str, Enum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"
    QUARANTINED = "quarantined"


def email_status(has_syntax: bool, has_mx: bool,
                 mailbox_confirmed: bool, catch_all: bool) -> Status:
    """The exact check behind an email's status word (S2 decision).

    verified   -> the mailbox itself was confirmed (SMTP probe accepted, or a
                  deliverability tool returned 'deliverable') on a non-catch-all
                  domain. Catch-all domains accept everything, so a passing probe
                  proves nothing there -> inferred.
    inferred   -> syntax + MX present but the mailbox was not confirmed.
    quarantined-> bad syntax or no MX: the value is withheld, not shipped.
    """
    if not has_syntax or not has_mx:
        return Status.QUARANTINED
    if mailbox_confirmed and not catch_all:
        return Status.VERIFIED
    return Status.INFERRED


# --- S2: contact route classification -----------------------------------------
class RouteType(str, Enum):
    PERSONAL = "personal"       # the person's own route (counts toward 200+)
    FIRM_LEVEL = "firm-level"   # company inbox / switchboard (does not count)


# Generic mailboxes that belong to the firm, never to a person.
GENERIC_LOCALPARTS = frozenset({
    "info", "contact", "hello", "admin", "office", "family", "team",
    "enquiries", "inquiries", "general", "mail", "email", "support",
    "welcome", "ir", "media", "press", "careers", "jobs", "hr",
    "reception", "frontdesk", "main", "noreply", "no-reply", "donotreply",
})


def _name_patterns(principal_name: str) -> set[str]:
    """Localpart forms that encode the listed principal's own name."""
    tokens = [t for t in re.split(r"[^a-z]+", (principal_name or "").lower()) if t]
    if not tokens:
        return set()
    first, last = tokens[0], tokens[-1]
    fi, li = first[0], last[0]
    return {
        first, last,
        first + last, last + first,
        fi + last, last + fi,
        first + li, li + first,
        fi + li, li + fi,
    }


def email_route(email: str, principal_name: str) -> RouteType:
    """personal only when the localpart encodes the LISTED principal's name.

    A generic mailbox, or an address naming a DIFFERENT person than the listed
    principal (the Stage-1 Stenger error), is firm-level and never counts as that
    principal's personal route.
    """
    local = (email or "").split("@", 1)[0].strip().lower()
    if not local or local in GENERIC_LOCALPARTS:
        return RouteType.FIRM_LEVEL
    local_norm = re.sub(r"[^a-z]", "", local)
    if local_norm and local_norm in _name_patterns(principal_name):
        return RouteType.PERSONAL
    return RouteType.FIRM_LEVEL


def counts_as_personal_gate(status: Status, route: RouteType) -> bool:
    """The 200+ hard gate: a contact counts only if verified AND personal."""
    return status == Status.VERIFIED and route == RouteType.PERSONAL


# --- S3: the two floors --------------------------------------------------------
def meets_inclusion_floor(category: FirmCategory, exists: bool,
                          function_proven: bool, entity_coherent: bool,
                          beyond_seed_cells: int) -> bool:
    """Truth floor to count toward the 500 (S3)."""
    return (counts_toward_500(category)
            and exists
            and function_proven
            and entity_coherent
            and beyond_seed_cells >= 1)


def meets_commercial_standard(has_decision_maker: bool,
                              has_focus_or_mandate: bool,
                              has_reachable_route: bool,
                              has_dated_signal: bool) -> bool:
    """Value floor that makes a record worth buying (S3)."""
    return (has_decision_maker
            and has_focus_or_mandate
            and has_reachable_route
            and has_dated_signal)
