"""S6 — whole-record entity resolution.

Every value in a record must belong to the SAME entity. This pass pins the
record's identity from its anchors (the firm's distinctive name token(s) + the
principal's name parts + its own web domain) and quarantines any high-value cell
that belongs to a different entity — the snow-crab defect class (fix#5).

Decisions encoded (user-authored):
- A recent_signal is kept only if its text mentions a firm distinctive token OR a
  principal name-part; otherwise it is unverified linkage and is quarantined.
- An email on a different CORPORATE domain than the firm's own is quarantined
  (public providers are exempt — those are a personal-route question, not an
  entity mismatch).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from pipeline.schema import CandidateFirm

# Generic words that carry no entity identity — dropped before matching so that
# "Family Office" / "Management" etc. never count as a distinctive anchor.
_GENERIC = {
    "family", "office", "offices", "single", "multi", "multifamily",
    "capital", "management", "mgmt", "group", "holdings", "partners",
    "advisors", "advisers", "associates", "wealth", "investments",
    "investment", "ventures", "fund", "funds", "trust", "global",
    "international", "company", "co", "corp", "corporation", "inc",
    "incorporated", "llc", "lp", "llp", "the", "of", "and", "for",
}

# Public mailbox providers — an address here is a personal-route question, not a
# wrong-entity signal, so domain-coherence skips them.
_PUBLIC_EMAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "ymail.com", "icloud.com", "me.com", "aol.com", "proton.me",
    "protonmail.com", "gmx.com", "mail.com",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def distinctive_tokens(firm_name: str) -> set[str]:
    """The firm's identity tokens, generic family-office words removed."""
    return {t for t in _tokens(firm_name) if t not in _GENERIC and len(t) >= 2}


def principal_parts(firm: CandidateFirm) -> set[str]:
    """Name parts of the listed principal (>=3 chars, to avoid stray initials)."""
    val = firm.principal_name.value if firm.principal_name else None
    return {t for t in _tokens(val) if len(t) >= 3}


def _identity_anchors(firm: CandidateFirm) -> set[str]:
    return distinctive_tokens(firm.firm_name) | principal_parts(firm)


def signal_coherent(firm: CandidateFirm) -> bool:
    """True unless a present recent_signal fails to name the firm or a principal.

    A blank signal is vacuously coherent (nothing to link). If the record has no
    identity anchor at all, a signal cannot be verified as belonging to it, so it
    is treated as incoherent (strict, per the locked decision)."""
    sig = firm.recent_signal
    if sig is None or sig.is_blank():
        return True
    anchors = _identity_anchors(firm)
    if not anchors:
        return False
    text = f"{sig.value or ''} {sig.source or ''}".lower()
    return any(a in text for a in anchors)


def _registrable(host: str) -> str:
    host = (host or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_of_url(url: str) -> str:
    if not url:
        return ""
    netloc = urlparse(url if "//" in url else "//" + url).netloc
    return _registrable(netloc)


def email_domain_coherent(firm: CandidateFirm) -> bool:
    """True unless the email sits on a different corporate domain than the firm's.

    Can't check without both a website domain and an email -> coherent. Public
    providers are exempt (personal-route question, not an entity mismatch)."""
    email = firm.principal_email.value if firm.principal_email else None
    if not email or "@" not in email or not firm.website:
        return True
    edom = _registrable(email.split("@", 1)[1])
    if edom in _PUBLIC_EMAIL:
        return True
    wdom = _domain_of_url(firm.website)
    if not wdom:
        return True
    return (edom == wdom
            or edom.endswith("." + wdom)
            or wdom.endswith("." + edom))


def resolve_entity(firm: CandidateFirm) -> CandidateFirm:
    """Quarantine cross-entity values and record whether the record is coherent."""
    if not firm.recent_signal.is_blank() and not signal_coherent(firm):
        firm.recent_signal.quarantine(
            "recent signal does not name the firm or its principals "
            "— unverified entity linkage")

    if not firm.principal_email.is_blank() and not email_domain_coherent(firm):
        firm.principal_email.quarantine(
            "email domain differs from the firm's own domain "
            "— belongs to a different entity")

    # After withholding cross-entity values, the record is coherent iff it has an
    # identity anchor we could pin it to; an anchorless name (headline debris) is
    # not a resolvable single entity.
    firm.entity_coherent = bool(_identity_anchors(firm))
    return firm
