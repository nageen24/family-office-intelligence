"""Free reach recovery for a function-proven firm with no personal route.

$0 only — the Serper LinkedIn path plus what the firm publishes on its own site:
  1. Re-fetch the team/leadership page and extract a NAMED principal (guarded
     against the firm name echoed back as a person).
  2. Serper LinkedIn lookup, slug name-matched to that principal — labelled
     'found via Serper, name-matched, not fetch-verified' (inferred).
  3. A direct/mobile phone published on the site — personal ONLY if the site
     labels it direct/mobile/cell, else it stays firm-level and does not count.

Every route is labelled exactly as found; nothing is guessed. A firm with no
reachable named person stays proven-but-unqualified.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.ontology import RouteType
from pipeline.enrichment.function_proof import fetch_people_text, fetch_site_text
from pipeline.enrichment.contacts import extract_principal, _looks_like_person, PRINCIPAL_SYSTEM

# A phone labelled direct/mobile/cell within a short window BEFORE the number is
# the person's own line; a bare/main/office number is firm-level.
_PHONE = r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
_DIRECT_PHONE = re.compile(r"(?:direct|mobile|cell|cellular|personal)\D{0,25}?(" + _PHONE + r")", re.I)


def _direct_phone(text: str) -> Optional[str]:
    m = _DIRECT_PHONE.search(text or "")
    return m.group(1).strip() if m else None


def recover_reach(firm: CandidateFirm, chat: Callable[[str, str], str],
                  serper=None,
                  people_fetch: Callable[[str], str] = fetch_people_text,
                  site_fetch: Callable[[str], str] = fetch_site_text) -> CandidateFirm:
    """Try to give a proven firm ONE personal route, free. Idempotent."""
    if not firm.website:
        return firm

    # 1. principal name from the team/leadership page (drop a firm-name echo first)
    if not firm.principal_name.is_blank() and not _looks_like_person(
            firm.principal_name.value, firm.firm_name):
        firm.principal_name = Cell()                     # clear the bad value
    people = people_fetch(firm.website) or ""
    if firm.principal_name.is_blank() and people:
        prin = extract_principal(people[:6000],
                                 lambda t: chat(PRINCIPAL_SYSTEM, t),
                                 firm_name=firm.firm_name)
        if prin:
            firm.principal_name = Cell(
                value=prin["name"], source=firm.website,
                method="named on the firm's own team/leadership page",
                epistemic=Epistemic.FACT, confidence=Confidence.HIGH)
            if prin["title"]:
                firm.principal_title = Cell(
                    value=prin["title"], source=firm.website,
                    method="title on the firm's own team/leadership page",
                    epistemic=Epistemic.FACT, confidence=Confidence.HIGH)

    # 2. Serper LinkedIn, slug name-matched to the principal (honest label)
    if not firm.principal_name.is_blank() and firm.principal_linkedin.is_blank():
        from pipeline.enrichment.serper import Serper, enrich_serper
        enrich_serper(firm, serper if serper is not None else Serper())

    # 3. a direct/mobile phone the site itself labels personal
    if firm.principal_phone.is_blank() or firm.principal_phone.route is not RouteType.PERSONAL:
        phone = _direct_phone(people) or _direct_phone(site_fetch(firm.website) or "")
        if phone:
            firm.principal_phone = Cell(
                value=phone, source=firm.website,
                method="direct/mobile line published on the firm's own site",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM,
                route=RouteType.PERSONAL)
    return firm
