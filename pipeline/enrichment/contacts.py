"""S11 — person-level contacts from the firm's OWN site (scrape-only).

Locked decision: no pattern-guessing. Candidate emails come only from the firm's
own pages and its own registrable domain. The principal name is extracted by an
LLM but code-verified to appear on the page (no hallucinated principals). The
personal email is the address whose local-part name-matches the listed principal;
generic mailboxes and cross-domain vendor addresses are not a personal route.

verified/mailbox-confirmation of the chosen email happens later in validation
(verify_email SMTP RCPT); here we only find the honest candidate.
"""
from __future__ import annotations

import json
import re
from typing import Callable, List, Optional
from urllib.parse import urlparse

from pipeline.ontology import quote_present, email_route, RouteType
from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.enrichment.function_proof import fetch_site_text, _parse_json

LlmFn = Callable[[str], str]
FetchFn = Callable[[str], str]

_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PLACEHOLDER = ("user@", "name@", "email@", "firstname", "lastname", "example.",
                "domain.com", "yourdomain", "sentry", "wixpress", "godaddy",
                "@2x", "@sentry")

PRINCIPAL_SYSTEM = (
    "From this firm's own website text, name the single most senior individual "
    "(founder / principal / managing partner / CEO). Return ONLY JSON: "
    'principal_name (verbatim as written on the page, else ""), principal_title '
    '(verbatim, else ""). Copy the name exactly as it appears; do not invent one.'
)


def _registrable(host: str) -> str:
    host = (host or "").lower().strip()
    return host[4:] if host.startswith("www.") else host


def same_domain_emails(text: str, site_url: str) -> List[str]:
    """Emails on the site's own registrable domain, placeholders removed."""
    dom = _registrable(urlparse(site_url).netloc)
    out = []
    for e in _EMAIL.findall(text or ""):
        el = e.lower()
        edom = _registrable(el.split("@", 1)[1])
        if edom != dom and not edom.endswith("." + dom):
            continue
        if any(p in el for p in _PLACEHOLDER):
            continue
        if el not in out:
            out.append(el)
    return out


def extract_principal(page_text: str, llm: LlmFn) -> Optional[dict]:
    data = _parse_json(llm(page_text))
    name = (data.get("principal_name") or "").strip()
    if not name or not quote_present(page_text, name):   # code-verify it's on the page
        return None
    return {"name": name, "title": (data.get("principal_title") or "").strip() or None}


def enrich_contacts(firm: CandidateFirm, llm: LlmFn,
                    fetch: FetchFn = fetch_site_text) -> CandidateFirm:
    """Set principal name/title and a scraped personal email from the own site."""
    if not firm.website:
        return firm
    page = fetch(firm.website)
    if not page:
        return firm

    prin = extract_principal(page, llm)
    if prin:
        firm.principal_name = Cell(
            value=prin["name"], source=firm.website,
            method="named on the firm's own website (team/about page)",
            epistemic=Epistemic.FACT, confidence=Confidence.HIGH)
        if prin["title"]:
            firm.principal_title = Cell(
                value=prin["title"], source=firm.website,
                method="title on the firm's own website",
                epistemic=Epistemic.FACT, confidence=Confidence.HIGH)

    # The personal email = a same-domain address that name-matches the principal.
    principal_name = firm.principal_name.value or ""
    for e in same_domain_emails(page, firm.website):
        if email_route(e, principal_name) is RouteType.PERSONAL:
            firm.principal_email = Cell(
                value=e, source=firm.website,
                method="scraped from the firm's own site; name-matched to principal",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)
            break
    return firm
