"""S19 — cross-run staleness/trust engine.

On a later run a firm's source is re-checked against what was stored. Locked rule:
- unchanged  -> trust=fresh, re-stamp last_verified.
- went dark  -> keep the (validly captured) proof, trust=stale, reason recorded,
               last_verified NOT advanced.
- contradicts (the proof sentence is gone from the live page) -> withhold the
               function proof, trust=contradicted (the record loses function and
               drops on re-validation).
"""
from pipeline.schema import CandidateFirm
from pipeline.staleness import needs_recheck, apply_recheck

PAGE = "About Acme. Acme is a multi-family office serving families. We invest broadly."
QUOTE = "Acme is a multi-family office serving families"


def _firm(last="2026-07-01"):
    f = CandidateFirm(firm_name="Acme Family Office", discovery_source="SEC Form ADV")
    f.website = "https://acme.com"
    f.proof_function_source = f.website
    f.proof_function_quote = QUOTE
    f.proof_type_quote = QUOTE
    f.last_verified = last
    f.trust = "fresh"
    return f


def test_unchanged_source_refreshes_trust():
    f = _firm()
    apply_recheck(f, PAGE, today="2026-08-04")
    assert f.trust == "fresh"
    assert f.last_verified == "2026-08-04"
    assert f.proof_function_quote == QUOTE


def test_dark_source_keeps_proof_but_marks_stale():
    f = _firm(last="2026-07-01")
    apply_recheck(f, None, today="2026-08-04")           # fetch returned nothing
    assert f.trust == "stale"
    assert f.proof_function_quote == QUOTE               # kept — was validly captured
    assert f.last_verified == "2026-07-01"               # NOT advanced
    assert "dark" in f.staleness_reason


def test_contradiction_withholds_the_function_proof():
    f = _firm()
    changed = "About Acme. Acme is a registered investment adviser to individuals."
    apply_recheck(f, changed, today="2026-08-04")
    assert f.trust == "contradicted"
    assert f.proof_function_quote is None                # withheld -> record will drop
    assert f.proof_type_quote is None


def test_needs_recheck_by_age():
    assert needs_recheck(_firm(last="2026-06-01"), today="2026-08-04", max_age_days=14)
    assert not needs_recheck(_firm(last="2026-08-03"), today="2026-08-04", max_age_days=14)
    # a firm never verified (no function proof) is not a re-check target
    fresh_never = CandidateFirm(firm_name="X", discovery_source="news")
    assert not needs_recheck(fresh_never, today="2026-08-04", max_age_days=14)
