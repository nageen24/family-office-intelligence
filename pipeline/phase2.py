"""S13 — Phase-2 orchestrator: discover -> beyond-seed enrich -> validate -> write.

Each firm's own site is fetched ONCE and shared by both beyond-seed extractors:
the function/type proof (Proof B/C) and the person-level contact (principal +
scraped personal email). The run is concurrent + rate-limited + fault-isolated
(pipeline.runner) so it can process thousands of candidates on free tiers.

The full climb to 500 happens across scheduled runs (Phase 3-4); this module is
the single reusable run body they call.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.ontology import email_route, RouteType
from pipeline.enrichment.function_proof import (
    fetch_site_text, extract_function_proof, SYSTEM as FUNCTION_SYSTEM)
from pipeline.enrichment.contacts import (
    extract_principal, same_domain_emails, PRINCIPAL_SYSTEM)

Chat2 = Callable[[str, str], str]     # (system, user) -> content


def enrich_one_firm(firm: CandidateFirm, chat: Chat2,
                    fetch: Callable[[str], str] = fetch_site_text,
                    ledger=None) -> CandidateFirm:
    """Fetch the firm's own site once; capture function/type proof + contacts."""
    if not firm.website:
        return firm
    page = fetch(firm.website)
    if ledger:
        ledger.bump("fetches")
    if not page:
        return firm

    # Proof B/C — function + type, each quote code-verified against the page.
    fn_llm = lambda text: chat(FUNCTION_SYSTEM, text)
    proof = extract_function_proof(page, fn_llm)
    if proof["function_quote"]:
        firm.proof_function_source = firm.website
        firm.proof_function_quote = proof["function_quote"]
        firm.proof_type_quote = proof["type_quote"]
        firm.sec_family_office_exemption = proof["sec_family_office_exemption"]

    # Person-level contact — principal (code-verified on page) + scraped personal email.
    prin_llm = lambda text: chat(PRINCIPAL_SYSTEM, text)
    prin = extract_principal(page, prin_llm)
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

    principal_name = firm.principal_name.value or ""
    for e in same_domain_emails(page, firm.website):
        if email_route(e, principal_name) is RouteType.PERSONAL:
            firm.principal_email = Cell(
                value=e, source=firm.website,
                method="scraped from the firm's own site; name-matched to principal",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)
            break
    return firm


def run_stage2(pool_name: str = "discovered", limit: Optional[int] = None,
               workers: int = 8, min_interval: float = 2.0,
               out_name: str = "stage2_enriched") -> dict:
    """Load a discovered pool, enrich beyond-seed concurrently, validate, report."""
    from pipeline.io_utils import load_pool, save_pool
    from pipeline.validation.validate import validate_all
    from pipeline.runner import Ledger, rate_limited, enrich_pool
    from rag.llm import chat

    pool: List[CandidateFirm] = load_pool(pool_name)
    if limit:
        pool = pool[:limit]

    ledger = Ledger()
    rl_chat = rate_limited(chat, min_interval=min_interval, ledger=ledger)
    enrich_pool(pool, lambda f: enrich_one_firm(f, rl_chat, ledger=ledger),
                workers=workers, ledger=ledger)

    validate_all(pool)
    ledger.bump("qualified", sum(1 for f in pool if f.record_status == "Qualified"))
    save_pool(pool, out_name)

    snap = ledger.snapshot()
    snap["input"] = len(pool)
    return snap
