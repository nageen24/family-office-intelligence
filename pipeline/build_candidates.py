"""Build the committed multi-source candidate pool (data/state/candidates.json).

Runs EVERY registered discovery source (a real mix, not one registry), dedups by
stable firm key, merges provenance + any dated signal, and orders website-first
then FO-name signal — so the climb spends its budget on firms it can actually
prove (Proof B needs the firm's own site). Name-only candidates (EDGAR/News/CIK/
990) are kept at the back; they become qualifiable once the browser layer finds
their website.

Regenerate:  python -m pipeline.build_candidates
"""
from __future__ import annotations

import pipeline.discovery  # noqa: F401  (registers all sources)
from pipeline.discovery.base import all_sources
from pipeline.schema import CandidateFirm
from pipeline.state import firm_key, save_state
from pipeline.discovery.sec_adv import priority_score as _adv_priority

# per-source caps (ADV is the backbone; others contribute breadth)
_LIMITS = {"SEC Form ADV (registered adviser roster)": 100000}
_DEFAULT_LIMIT = 400


def _merge(into: CandidateFirm, other: CandidateFirm) -> None:
    """Fold a duplicate's useful fields into the kept record."""
    if not into.website and other.website:
        into.website = other.website
    if into.recent_signal.is_blank() and not other.recent_signal.is_blank():
        into.recent_signal = other.recent_signal
    if not into.cik and other.cik:
        into.cik = other.cik
    # record that more than one source found it
    if other.discovery_source not in (into.discovery_source or ""):
        into.discovery_source = f"{into.discovery_source} + {other.discovery_source}"


def build_pool() -> list[CandidateFirm]:
    by_key: dict[str, CandidateFirm] = {}
    for src in all_sources():
        limit = _LIMITS.get(src.name, _DEFAULT_LIMIT)
        try:
            found = src.discover(limit=limit)
        except Exception as e:  # a flaky/blocked source must not sink the rest
            print(f"[build] {src.name}: {type(e).__name__}: {str(e)[:60]}")
            continue
        print(f"[build] {src.name}: +{len(found)}")
        for f in found:
            k = firm_key(f)
            if k in by_key:
                _merge(by_key[k], f)
            else:
                by_key[k] = f

    pool = list(by_key.values())

    def sort_key(f: CandidateFirm):
        # website-first, then a family-office name signal, then a dated signal
        name = f.firm_name or ""
        fo = 1 if _adv_priority({"Primary Business Name": name, "Legal Name": name,
                                 "5D(b)(1)": "0"}) >= 40 else 0
        return (1 if f.website else 0, fo, 0 if f.recent_signal.is_blank() else 1)

    pool.sort(key=sort_key, reverse=True)
    return pool


def _name_only_rank(f: CandidateFirm) -> int:
    """Sort key for name-only firms: registered ENTITIES before headline debris.

    EDGAR / 990 / CIK / Wikidata are real registered entities whose name is worth
    a browser website lookup. Google News RSS 'firms' are headline fragments (e.g.
    'Mega-IPOs Impact Family Office') that waste the browser and, when a weak name
    match sticks, attach a junk site. Rank News last so the browser spends its
    effort on the SFO-rich registered entities first."""
    src = (f.discovery_source or "").lower()
    return 1 if ("news" in src and "edgar" not in src and "cik" not in src
                 and "990" not in src) else 0


def interleave_name_only(pool: list[CandidateFirm], every: int = 4):
    """Interleave the name-only firms (EDGAR/990/News/CIK — no website) THROUGH
    the website-bearing firms instead of leaving them all at the back.

    A pure website-first sort meant the climb only ever reached ADV firms; the
    ~640 name-only firms (SFO-rich, and reachable once the browser layer finds
    their site) sat behind 3,200 ADV rows and were never attempted in the window.
    This emits (every-1) website firms then 1 name-only, repeating, so source mix
    is spread across every batch. Website firms keep their incoming order; name-
    only firms are ordered registered-entities-first (News RSS debris last)."""
    have = [f for f in pool if f.website]
    none = sorted((f for f in pool if not f.website), key=_name_only_rank)
    out: list[CandidateFirm] = []
    hi = ni = 0
    while hi < len(have) or ni < len(none):
        for _ in range(every - 1):
            if hi < len(have):
                out.append(have[hi]); hi += 1
        if ni < len(none):
            out.append(none[ni]); ni += 1
    return out




def main():
    pool = build_pool()
    state = {}
    for f in pool:
        state.setdefault(firm_key(f), f)
    save_state("data/state/candidates.json", state)
    with_site = sum(1 for f in pool if f.website)
    print(f"\ncandidates: {len(state)}  with_website: {with_site}")


if __name__ == "__main__":
    main()
