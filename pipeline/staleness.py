"""S19 — cross-run staleness/trust engine.

The climb keeps durable per-firm state across runs. This module re-checks a firm's
source on a later run and adjusts trust, per the locked rule:

- unchanged   -> trust "fresh", last_verified re-stamped to today.
- went dark   -> keep the validly-captured proof, trust "stale", reason recorded,
                 last_verified left as-is (going dark does not make the past proof
                 false, but it can no longer be re-confirmed).
- contradicts -> the function-proof sentence is gone from the live page, so the
                 proof is WITHHELD (trust "contradicted"); the record loses its
                 function proof and drops when re-validated.

Only firms whose function was proven are re-check targets; a firm with no proof has
nothing to keep fresh.
"""
from __future__ import annotations

from datetime import date, datetime

from pipeline.schema import CandidateFirm
from pipeline.ontology import quote_present


def _age_days(last_verified: str, today: str) -> int:
    try:
        d0 = datetime.strptime(last_verified[:10], "%Y-%m-%d").date()
        d1 = datetime.strptime(today[:10], "%Y-%m-%d").date()
        return (d1 - d0).days
    except Exception:
        return 10 ** 6


def needs_recheck(firm: CandidateFirm, today: str | None = None,
                  max_age_days: int = 14) -> bool:
    """True when a proven firm's source is older than max_age_days."""
    if not firm.proof_function_quote:
        return False
    today = today or date.today().isoformat()
    if not firm.last_verified:
        return True
    return _age_days(firm.last_verified, today) >= max_age_days


def apply_recheck(firm: CandidateFirm, fresh_page: str | None,
                  today: str | None = None) -> CandidateFirm:
    """Re-evaluate one firm's source against a freshly fetched page (or None)."""
    today = today or date.today().isoformat()
    if not firm.proof_function_quote:
        return firm

    if not fresh_page:                                   # source went dark
        firm.trust = "stale"
        firm.staleness_reason = (
            f"source went dark on re-check {today}; kept the proof captured "
            f"{firm.last_verified} but it can no longer be re-confirmed")
        return firm                                      # keep value, don't advance date

    if quote_present(fresh_page, firm.proof_function_quote):
        firm.trust = "fresh"
        firm.last_verified = today
        firm.staleness_reason = None
        return firm

    # contradiction: the proof sentence is no longer on the live page
    firm.trust = "contradicted"
    firm.staleness_reason = (
        f"function-proof sentence no longer present on the live site (re-check "
        f"{today}) — proof withheld")
    firm.proof_function_quote = None
    firm.proof_type_quote = None
    return firm
