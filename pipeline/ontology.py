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


# --- family-office FUNCTION gate (proof-standard tightening) --------------------
# A quote proves FO-function ONLY if the firm states it IS or OPERATES AS a family
# office (single or multi). Serving wealthy families, offering "family office
# services" as a service line, a family-related NAME, or being a "family-owned"
# advisory firm do NOT qualify (per the brief). This is a mechanical control on
# the quote text, not a matter of trusting the model.
import re as _re2
_FO_PHRASE = r"(?:single[\s-]?|multi[\s-]?)?family[\s-]?office"
# The PREDICATE noun must be SINGULAR: '... is a multi-family office' (being one),
# not '... to family officeS' (serving/among others).
_FO_SINGULAR = r"(?:single[\s-]?|multi[\s-]?)?family[\s-]?office(?!s)"
# Up to 3 ADJECTIVE words (independent, outsourced, boutique, ...) with optional
# commas may sit between the article and the phrase, but NOT a preposition/verb
# (to / for / of / as / with / serving) — those signal serving-others, not being-one.
_ADJ_GAP = r"(?:(?!(?:to|for|of|as|with|serv\w*)\b)[a-z][a-z'-]*,?\s+){0,3}"

# The firm identifies AS a family office: copula / operates-as / functions-as /
# serves-as / structured-as, then an optional article + adjective gap + the phrase.
_FO_IDENTITY = _re2.compile(
    r"\b(?:is|are|being|remains?|"
    r"operates?\s+as|operating\s+as|"
    r"serves?\s+as|serving\s+as|serve\s+as|"
    r"functions?\s+as|functioning\s+as|acts?\s+as|acting\s+as|"
    r"structured\s+as|set\s+up\s+as|established\s+as|known\s+as|built\s+as)\s+"
    r"(?:an?\s+|the\s+)?" + _ADJ_GAP + _FO_SINGULAR, _re2.I)


def establishes_fo_function(quote: str) -> bool:
    """True only if the quote STATES the firm is / operates as a family office.

    Passes: 'We are a single-family office', 'operates as a multi-family office',
    'Colony Family Offices is an independent, multi-family office'. Fails: 'serves
    wealthy families', 'family office services', 'family-owned RIA', 'advisor to
    family offices', a firm merely NAMED '... Family Office' that only 'delivers
    family office services'."""
    ql = (quote or "").lower()
    if not _re2.search(_FO_PHRASE, ql):     # must actually mention a family office
        return False
    return bool(_FO_IDENTITY.search(ql))


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
                          beyond_seed_cells: int,
                          has_personal_reach: bool) -> bool:
    """Truth floor to count toward the 500 (S3).

    has_personal_reach (user tightening): a record counts only if it exposes a
    real way to reach the NAMED person — their own email, own direct phone, or own
    LinkedIn. A firm switchboard or an info@ inbox is not a personal route, so a
    firm with only function proof and no reachable person does NOT count.
    """
    return (counts_toward_500(category)
            and exists
            and function_proven
            and entity_coherent
            and beyond_seed_cells >= 1
            and has_personal_reach)


def meets_commercial_standard(has_decision_maker: bool,
                              has_focus_or_mandate: bool,
                              has_reachable_route: bool,
                              has_dated_signal: bool) -> bool:
    """Value floor that makes a record worth buying (S3)."""
    return (has_decision_maker
            and has_focus_or_mandate
            and has_reachable_route
            and has_dated_signal)
