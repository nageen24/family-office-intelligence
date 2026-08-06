"""S10 — enrichment-beyond-seed: capture a code-verified FO-function proof.

Discovery (S9) proves a firm EXISTS. This step goes BEYOND the discovery source
to the firm's OWN website and captures Proof B (function) + Proof C (type):

  1. Fetch the firm's own site (homepage + an about page). Direct fetches work
     from this environment; only search engines are IP-blocked.
  2. An LLM reads the page and returns the VERBATIM sentence proving FO-function
     and, if present, the sentence proving single- vs multi-family.
  3. CODE verifies each quote literally exists on the page (ontology.quote_present).
     A hallucinated/paraphrased quote is dropped — the control is mechanical, not
     a matter of trusting the model.

Only quotes that survive step 3 become proof. Registration/name/press never do.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

import requests

from pipeline.ontology import quote_present, establishes_fo_function
from pipeline.schema import CandidateFirm
from pipeline.discovery.base import USER_AGENT

LlmFn = Callable[[str], str]
FetchFn = Callable[[str], str]

SYSTEM = (
    "You read one company's OWN website text and decide, strictly from that text, "
    "whether the company states it IS or OPERATES AS a family office (single- or "
    "multi-family). You never guess from the name. A firm that merely SERVES "
    "wealthy families, offers 'family office services' as one service line, is a "
    "'family-owned' advisory firm, or is just NAMED with 'family' does NOT "
    "qualify — is_family_office must be false in those cases. Return ONLY JSON "
    "with these keys:\n"
    '  is_family_office (bool), function_quote (a VERBATIM sentence copied exactly '
    'from the text in which the firm states it IS or OPERATES AS a family office, '
    'else ""), '
    'type ("single"|"multi"|"unknown"), type_quote (a VERBATIM sentence proving '
    'single- vs multi-family, else ""), sec_family_office_exemption (bool: does '
    "the text claim an SEC family-office exemption / Rule 202(a)(11)(G)-1), "
    'investing_focus (a VERBATIM sentence copied exactly from the text describing '
    'WHAT or HOW the firm invests — asset classes, sectors, strategy, or mandate — '
    'else "").\n'
    "Every quote MUST be copied character-for-character from the text. If nothing "
    "in the text states family-office function, set is_family_office false and "
    "leave quotes empty."
)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def extract_function_proof(page_text: str, llm: LlmFn) -> dict:
    """Return only quotes the model produced AND code verified against the page.

    `no_proof_reason` says WHY no function quote survived (None on success):
    llm-response-unparseable / no-proof-language-found / quote-not-verbatim.
    """
    data = _parse_json(llm(page_text))
    fq = (data.get("function_quote") or "").strip()
    tq = (data.get("type_quote") or "").strip()
    focus = (data.get("investing_focus") or "").strip()

    # The mechanical control: a quote counts only if it is literally on the page
    # AND states the firm IS / operates as a family office (not merely serves
    # families or lists 'family office services').
    no_proof_reason = None
    if not data:
        fq, no_proof_reason = None, "llm-response-unparseable"
    elif not (data.get("is_family_office") and fq):
        fq, no_proof_reason = None, "no-proof-language-found"
    elif not quote_present(page_text, fq):
        fq, no_proof_reason = None, "quote-not-verbatim"
    elif not establishes_fo_function(fq):
        fq, no_proof_reason = None, "not-fo-identity-statement"
    if not (tq and quote_present(page_text, tq)):
        tq = None
    if not (focus and quote_present(page_text, focus)):
        focus = None

    return {
        "no_proof_reason": no_proof_reason,
        "function_quote": fq,
        "type_quote": tq if fq else None,      # type is meaningless without function
        "sec_family_office_exemption": bool(data.get("sec_family_office_exemption")) if fq else False,
        "investing_focus": focus if fq else None,   # focus only for a proven FO
    }


_LI_IN = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+", re.I)


def _candidate_bases(url: str) -> list[str]:
    """Base URLs to try: https preferred, and toggle www — ADV stores stale
    http://www. URLs but many firm sites are https-only or non-www."""
    from urllib.parse import urlparse
    p = urlparse(url if "//" in url else "https://" + url)
    host = p.netloc or p.path
    hosts = [host, host[4:]] if host.startswith("www.") else [host, "www." + host]
    bases = [f"{scheme}://{h}" for scheme in ("https", "http") for h in hosts if h]
    return list(dict.fromkeys(bases))


def _get(u: str, timeout: int = 8):
    try:
        r = requests.get(u, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": USER_AGENT})
    except requests.RequestException:
        return None
    ct = r.headers.get("content-type", "").lower()
    if r.status_code < 400 and ("html" in ct or "<html" in r.text[:2000].lower()):
        return r
    return None


def fetch_site_text(url: str, max_chars: int = 9000) -> str:
    """Homepage + team/about pages, stripped to visible text.

    Robust to stale http/www URLs (tries https + www toggles), lenient on status/
    content-type, and includes team pages (where a firm 'shows its people'). Any
    LinkedIn PROFILE URLs in the raw hrefs are appended so the contact extractor
    can see them (tag-stripping would otherwise drop them)."""
    from urllib.parse import urljoin
    base = next((b for b in _candidate_bases(url) if _get(b, timeout=6)), None)
    if not base:
        return ""
    texts, links = [], []
    ok = 0
    # Try a handful of common pages, but stop once we have enough content or have
    # made too many attempts — a firm with many slow/404 paths must not hang.
    for suffix in ("", "about", "about-us", "team", "our-team", "people",
                   "leadership", "contact"):
        r = _get(urljoin(base + "/", suffix))
        if r is not None:
            texts.append(_visible_text(r.text))
            links += _LI_IN.findall(r.text)
            ok += 1
        if sum(len(t) for t in texts) >= max_chars or ok >= 4:
            break
    body = " ".join(texts)[:max_chars]
    uniq = " ".join(dict.fromkeys(links))
    return (body + " " + uniq).strip() if uniq else body


_PEOPLE_SUFFIXES = ("team", "our-team", "people", "our-people", "leadership",
                    "management", "partners", "principals", "advisors", "advisers",
                    "about", "about-us", "who-we-are", "staff", "professionals")


def fetch_people_text(url: str, max_chars: int = 8000) -> str:
    """People-focused fetch: team / leadership / about pages FIRST.

    Principal names usually live off the homepage, so the homepage-first window the
    proof fetch uses can truncate them away. This fetches the people pages directly
    so a name lands in the LLM window. The honesty control is unchanged downstream —
    quote_present still verifies any extracted name is literally in this text."""
    from urllib.parse import urljoin
    base = next((b for b in _candidate_bases(url) if _get(b, timeout=6)), None)
    if not base:
        return ""
    texts, links, ok = [], [], 0
    for suffix in _PEOPLE_SUFFIXES:
        r = _get(urljoin(base + "/", suffix))
        if r is not None:
            texts.append(_visible_text(r.text))
            links += _LI_IN.findall(r.text)
            ok += 1
        if sum(len(t) for t in texts) >= max_chars or ok >= 4:
            break
    body = " ".join(texts)[:max_chars]
    uniq = " ".join(dict.fromkeys(links))
    return (body + " " + uniq).strip() if uniq else body


def _visible_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def enrich_function(firm: CandidateFirm, llm: LlmFn,
                    fetch: FetchFn = fetch_site_text) -> CandidateFirm:
    """Fetch the firm's own site and set the Proof B/C fields from verified quotes."""
    if not firm.website:
        return firm                      # no own site -> cannot prove function here
    page = fetch(firm.website)
    if not page:
        return firm
    proof = extract_function_proof(page, llm)
    if proof["function_quote"]:
        firm.proof_function_source = firm.website
        firm.proof_function_quote = proof["function_quote"]
        firm.proof_type_quote = proof["type_quote"]
        firm.sec_family_office_exemption = proof["sec_family_office_exemption"]
    return firm
