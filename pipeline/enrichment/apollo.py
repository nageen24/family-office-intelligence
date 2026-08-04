"""Apollo (free tier) — a contact-data PROVIDER source, entered through the pipeline.

Reach data (LinkedIn, personal email) is not obtainable from public/free search at
$0 (see docs/DATA_HONEST_LIMITS.md — Bing/DDG/JS-render all walled). Apollo fills
that gap, but it does NOT get to self-certify:

- OUR validation: the returned profile must match the named principal AND the
  current firm before we trust anything (no attributing a stranger or an ex-employee).
- HONEST labels: everything Apollo returns is `inferred` (provider-returned), NEVER
  `verified`. An Apollo email is a personal reach route, but counts toward the 200
  VERIFIED emails only if it separately passes our own SMTP mailbox check.
- CREDIT DISCIPLINE: LinkedIn (which recovers the reach gate) is fetched first;
  the scarce free-tier email credits are spent only on the strongest records.

The HTTP client is injected so validation/labeling is tested without the API.
"""
from __future__ import annotations

import os
import re
from typing import Callable, Optional

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.ontology import Status, RouteType
from pipeline.validation.entity import distinctive_tokens

# client(kind, **params) -> person dict | None ; kind in {"match","search"}
Client = Callable[..., Optional[dict]]


def _tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z]+", (s or "").lower()) if len(t) >= 3]


def _person_name(person: dict) -> str:
    return (person.get("name")
            or f"{person.get('first_name','')} {person.get('last_name','')}".strip())


def validate_person(person: dict, principal_name: str, firm_name: str) -> bool:
    """The returned profile must match the current FIRM, and (if we already have a
    principal) the named PERSON. Otherwise we do not trust it."""
    org = person.get("organization") or {}
    org_blob = f"{org.get('name','')} {org.get('primary_domain','')}".lower()
    firm_toks = distinctive_tokens(firm_name)
    firm_ok = bool(firm_toks) and any(t in org_blob for t in firm_toks)

    if principal_name:
        ptoks, ntoks = _tokens(principal_name), _tokens(_person_name(person))
        name_ok = bool(ptoks) and ptoks[0] in ntoks and ptoks[-1] in ntoks
    else:
        name_ok = True                      # discovering the name from Apollo
    return firm_ok and name_ok


def is_strong(firm: CandidateFirm) -> bool:
    """Worth spending a scarce email credit on: function-proven AND carries real
    intelligence (an investing focus AND a dated signal)."""
    return (bool(firm.proof_function_quote or firm.sec_family_office_exemption)
            and not firm.investing_thesis.is_blank()
            and not firm.recent_signal.is_blank())


def _domain(url: str) -> Optional[str]:
    from urllib.parse import urlparse
    if not url:
        return None
    host = urlparse(url if "//" in url else "//" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


def enrich_apollo(firm: CandidateFirm, client: Client,
                  reveal_email: bool = False) -> CandidateFirm:
    """Match the firm's principal via Apollo; set LinkedIn/title/(email) with honest
    provider-returned labels, only after our own name+firm validation passes."""
    domain = _domain(firm.website)
    pn = firm.principal_name.value or ""
    if pn:
        parts = pn.split()
        person = client("match", first_name=parts[0], last_name=parts[-1],
                        organization_name=firm.firm_name, domain=domain,
                        reveal_email=reveal_email)
    else:
        person = client("search", organization_name=firm.firm_name, domain=domain,
                        reveal_email=reveal_email)

    if not person or not validate_person(person, pn, firm.firm_name):
        return firm

    prov = "provider-returned by Apollo; profile name + current-firm matched by us"

    if firm.principal_name.is_blank() and _person_name(person):
        firm.principal_name = Cell(
            value=_person_name(person), source="Apollo", method=prov,
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            status=Status.INFERRED)

    li = person.get("linkedin_url") or ""
    if "linkedin.com/in/" in li:
        firm.principal_linkedin = Cell(
            value=li, source="Apollo",
            method=prov + "; not independently verified",
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            status=Status.INFERRED, route=RouteType.PERSONAL)

    if person.get("title") and firm.principal_title.is_blank():
        firm.principal_title = Cell(
            value=person["title"], source="Apollo", method=prov,
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            status=Status.INFERRED)

    email = person.get("email") or ""
    if reveal_email and "@" in email and "not_unlocked" not in email:
        firm.principal_email = Cell(
            value=email, source="Apollo",
            method=prov + "; NOT mailbox-verified (provider-returned, not verified)",
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            status=Status.INFERRED, route=RouteType.PERSONAL)
    return firm


class ApolloClient:
    """Live Apollo People API client (free tier). Needs APOLLO_API_KEY."""

    BASE = "https://api.apollo.io/api/v1"

    def __init__(self, key: Optional[str] = None):
        self.key = key or os.getenv("APOLLO_API_KEY")

    def __call__(self, kind: str, **params) -> Optional[dict]:
        if not self.key:
            return None
        import requests
        headers = {"X-Api-Key": self.key, "Content-Type": "application/json"}
        try:
            if kind == "match":
                body = {"first_name": params.get("first_name"),
                        "last_name": params.get("last_name"),
                        "organization_name": params.get("organization_name"),
                        "domain": params.get("domain"),
                        "reveal_personal_emails": bool(params.get("reveal_email"))}
                r = requests.post(f"{self.BASE}/people/match", json=body,
                                  headers=headers, timeout=20)
                return (r.json() or {}).get("person") if r.ok else None
            # kind == "search": senior person at the firm
            body = {"q_organization_domains": params.get("domain") or "",
                    "organization_names": [params.get("organization_name") or ""],
                    "person_seniorities": ["owner", "founder", "c_suite", "partner"],
                    "per_page": 1}
            r = requests.post(f"{self.BASE}/mixed_people/search", json=body,
                              headers=headers, timeout=20)
            people = (r.json() or {}).get("people") if r.ok else None
            return people[0] if people else None
        except requests.RequestException:
            return None
