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
    fetch_site_text, fetch_people_text, extract_function_proof,
    SYSTEM as FUNCTION_SYSTEM)
from pipeline.enrichment.contacts import (
    extract_principal, same_domain_emails, extract_person_linkedin, PRINCIPAL_SYSTEM)

Chat2 = Callable[[str, str], str]     # (system, user) -> content


def _distinctive_in(firm_name: str, text: str) -> bool:
    from pipeline.validation.entity import distinctive_tokens
    toks = distinctive_tokens(firm_name)
    low = (text or "").lower()
    return bool(toks) and all(t in low for t in list(toks)[:2])


def enrich_one_firm(firm: CandidateFirm, chat: Chat2,
                    fetch: Callable[[str], str] = fetch_site_text,
                    ledger=None, use_browser: bool = False,
                    add_news: bool = True,
                    people_fetch: Callable[[str], str] = fetch_people_text) -> CandidateFirm:
    """Fetch the firm's own site once; capture function/type proof + contacts.

    With use_browser, a name-only firm (no website) gets one via a rendered search
    (verified by name-match before trust), and a JS-thin page is supplemented with
    a rendered fetch so LinkedIn profiles behind JS become visible."""
    if not firm.website and use_browser:
        from pipeline.enrichment.render import find_website
        cand = find_website(firm.firm_name)
        if cand and _distinctive_in(firm.firm_name, fetch(cand) or ""):
            firm.website = cand
            firm.proof_exists = (firm.proof_exists or
                                 f"website found + name-verified via browser search: {cand}")
    if not firm.website:
        firm.fail_reason = "no-website"
        return firm
    page = fetch(firm.website)
    if ledger:
        ledger.bump("fetches")
    if use_browser and (not page or "linkedin.com/in" not in page):
        from pipeline.enrichment.render import render_text
        rendered = render_text(firm.website)
        if rendered:
            page = f"{page} {rendered}"[:12000] if page else rendered
    if not page:
        firm.fail_reason = "fetch-error"
        return firm

    # Cap the text sent to the LLM to control tokens-per-minute against the free
    # tier (mass 429s came from oversized contexts). quote_present verifies against
    # this SAME text, so proofs stay honest. Full page is kept for the cheap regex
    # scraping (emails / LinkedIn) below.
    llm_page = page[:6000]

    # Proof B/C — function + type, each quote code-verified against the page.
    fn_llm = lambda text: chat(FUNCTION_SYSTEM, text)
    try:
        proof = extract_function_proof(llm_page, fn_llm)
    except Exception as e:
        # chat() exhausted its retries — record why THIS firm failed before the
        # exception reaches the pool's fault isolation (firm retried next run).
        firm.fail_reason = f"llm-error: {type(e).__name__}: {str(e)[:80]}"
        raise
    firm.fail_reason = proof["no_proof_reason"]
    if proof["function_quote"]:
        firm.proof_function_source = firm.website
        firm.proof_function_quote = proof["function_quote"]
        firm.proof_type_quote = proof["type_quote"]
        firm.sec_family_office_exemption = proof["sec_family_office_exemption"]
        # what they invest in — verbatim from the firm's own site (code-verified)
        if proof.get("investing_focus"):
            firm.investing_thesis = Cell(
                value=proof["investing_focus"], source=firm.website,
                method="investing focus stated on the firm's own website (verbatim)",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM)

    # Person-level contact — principal (code-verified on page) + scraped personal email.
    prin_llm = lambda text: chat(PRINCIPAL_SYSTEM, text)
    prin = extract_principal(llm_page, prin_llm)
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

    # Name-focused fallback: a principal usually lives on the /team or /leadership
    # page, which can fall outside the homepage-first 6000-char window above — the
    # reason many function-proven firms carried no name. Only when no name was found
    # (so no extra cost on the common path), fetch the people pages specifically and
    # retry; quote_present still verifies the name is literally on that text.
    people_page = ""
    if firm.principal_name.is_blank() and firm.website:
        people_page = people_fetch(firm.website) or ""
        if ledger and people_page:
            ledger.bump("fetches")
        if people_page:
            prin = extract_principal(people_page[:6000], prin_llm)
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

    # Scrape the personal email / LinkedIn from the primary page AND, if we fetched
    # one, the people page (where a person's own address/profile usually sits).
    scrape_text = f"{page} {people_page}" if people_page else page
    principal_name = firm.principal_name.value or ""
    for e in same_domain_emails(scrape_text, firm.website):
        if email_route(e, principal_name) is RouteType.PERSONAL:
            firm.principal_email = Cell(
                value=e, source=firm.website,
                method="scraped from the firm's own site; name-matched to principal",
                epistemic=Epistemic.FACT, confidence=Confidence.MEDIUM,
                route=RouteType.PERSONAL)
            break

    # The person's own LinkedIn — a real personal route when no email is published.
    li = extract_person_linkedin(scrape_text, principal_name)
    if li:
        firm.principal_linkedin = Cell(
            value=li, source=firm.website,
            method="person's LinkedIn linked from the firm's own site; name-matched",
            epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
            route=RouteType.PERSONAL)

    # "Why now" — most recent dated news activity (entity-coherence is enforced in
    # validation, so a wrong-firm story is quarantined, not shipped).
    if add_news:
        try:
            from pipeline.enrichment.news_signal import NewsSignalEnricher
            NewsSignalEnricher().enrich(firm)
        except Exception:
            pass
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
