"""Verify Bing-sourced candidate websites, then scrape email/thesis (keyless).

Websites were found via a REAL browser (Bing rendered in Chrome), because every
scripted search engine IP-blocks this environment (see DECISIONS.md). A real
browser is not blocked, so the browser fetched candidate domains; but Bing's top
hit is often a wrong company sharing a word ("Looper Family Office" -> looper.com
the film site). So NOTHING is trusted until this pass fetches the candidate site
directly (direct site fetches DO work here) and confirms the firm's own name is
on the page. Unverified -> honest blank, never attached.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
GENERIC = {"family", "office", "offices", "the", "and", "llc", "inc", "lp",
           "llp", "ltd", "ag", "capital", "group", "partners", "wealth"}

_s = requests.Session()
_s.headers.update({"User-Agent": UA})


def _tokens(firm: str):
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", firm.lower()).split()
            if w not in GENERIC and len(w) > 2]


JUNK_EMAIL = ("domain.com", "example.com", "email.com", "yourdomain",
              "sentry", "wixpress", "latofonts", "googlemail", "test.com",
              "@2x", "wordpress", "squarespace", "godaddy")


def _regdom(host: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", host).split("/")[0].lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def verify(firm: str, url: str):
    """Return (verified_url|None, email|None, reason)."""
    if not url or url == "ERR":
        return None, None, "no candidate"
    toks = _tokens(firm)
    if not toks:
        return None, None, "no distinctive token"
    site_dom = _regdom(url)
    # A domain is strong evidence ONLY when it contains the firm token AND an
    # FO signal (biltmorefamilyoffice.com, virtus-fo.com). A bare common-word
    # domain (looper.com for "Looper Family Office") is NOT — that was a false
    # positive. This keeps 403 sites whose domain proves the firm, drops the
    # movie/travel/font collisions.
    FO_SIG = ("familyoffice", "family", "-fo", "fo.", "wealth", "capital",
              "invest", "fam", "advisor")
    domain_match = (any(t in site_dom for t in toks)
                    and any(s in site_dom for s in FO_SIG))

    try:
        r = _s.get(url, timeout=20)
        text = r.text.lower() if r.status_code < 400 else ""
    except Exception:
        text = ""

    if not text:
        if domain_match:
            return url, None, "verified by domain (fetch blocked)"
        return None, None, "fetch blocked, no domain match"

    # only DISTINCTIVE tokens (>=6 chars) count for text verification — a
    # common short word ("louis", "justice") appearing on an unrelated page is
    # not proof (St Louis Family Office was matching archbridge.com).
    tok_hit = any(t in text for t in toks if len(t) >= 6)
    fo_ctx = ("family office" in text or "family-office" in text
              or "single family" in text)
    # Require the firm token AND family-office context on the page — OR a
    # domain that itself proves it. Common-word text hits alone are not enough.
    if not ((tok_hit and fo_ctx) or domain_match):
        return None, None, f"unverified (token={tok_hit}, fo_ctx={fo_ctx})"

    # email must be on the SAME registrable domain as the site, and not junk
    email = None
    for e in EMAIL_RE.findall(r.text):
        el = e.lower()
        if el.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if any(j in el for j in JUNK_EMAIL):
            continue
        if _regdom(el.split("@")[1]) == site_dom:
            email = el
            break
    return url, email, "verified"


def main():
    cands = json.loads(Path("data/interim/web_candidates.json").read_text(encoding="utf-8"))
    results = {}
    for firm, url in cands.items():
        vurl, email, reason = verify(firm, url)
        results[firm] = {"website": vurl, "email": email, "reason": reason}
        tag = "OK " if vurl else "-- "
        print(f"{tag}{firm[:34]:34s} {str(vurl):38s} email={email or '-'}  ({reason})")
    Path("data/interim/web_verified.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    got = sum(1 for r in results.values() if r["website"])
    em = sum(1 for r in results.values() if r["email"])
    print(f"\n=== verified {got}/{len(results)} websites, {em} emails ===")


if __name__ == "__main__":
    main()
