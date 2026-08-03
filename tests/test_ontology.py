"""Tests for the Stage-2 ontology enforcement layer (pipeline/ontology.py).

These encode the locked S1-S3 decisions as executable controls:
- 5 firm categories and which count toward the 500 (S1).
- The quote-existence check behind meaning-based type detection (S1).
- The 4 status words and the exact per-value check behind each (S2, email).
- personal vs firm-level route classification (S2).
- inclusion floor and commercial standard predicates (S3).

They are the "controls in code, not prompts" the assessment scores, so each
predicate is tested for both the pass and the fail path.
"""
from pipeline.ontology import (
    FirmCategory, Status, RouteType,
    counts_toward_500, quote_present,
    email_status, email_route, counts_as_personal_gate,
    meets_inclusion_floor, meets_commercial_standard,
)


# --- S1: categories and which count -------------------------------------------
def test_qualifying_categories_count_toward_500():
    assert counts_toward_500(FirmCategory.SFO)
    assert counts_toward_500(FirmCategory.MFO)
    assert counts_toward_500(FirmCategory.FO_TYPE_UNKNOWN)


def test_nonqualifying_categories_do_not_count():
    assert not counts_toward_500(FirmCategory.RIA_NONQUALIFYING)
    assert not counts_toward_500(FirmCategory.UNRESOLVED_QUARANTINE)


# --- S1: quote-existence check (meaning read by LLM, existence checked by code)-
def test_quote_present_accepts_literal_quote_ignoring_whitespace_and_case():
    source = "Acme is  the   Single Family Office of the Doe family.\nEst 1990."
    quote = "single family office of the doe family"
    assert quote_present(source, quote)


def test_quote_present_rejects_a_quote_not_in_the_source():
    source = "Acme provides wealth management advisory services to clients."
    quote = "single family office of the Doe family"
    assert not quote_present(source, quote)


def test_quote_present_rejects_empty_quote():
    assert not quote_present("any source text", "")


# --- S2: email status (verified = mailbox-confirmed only) ----------------------
def test_email_verified_only_when_mailbox_confirmed():
    assert email_status(has_syntax=True, has_mx=True,
                        mailbox_confirmed=True, catch_all=False) == Status.VERIFIED


def test_email_mx_only_is_inferred_not_verified():
    assert email_status(has_syntax=True, has_mx=True,
                        mailbox_confirmed=False, catch_all=False) == Status.INFERRED


def test_email_catch_all_is_inferred_even_if_probe_accepts():
    # a catch-all domain accepts everything, so a passing probe proves nothing
    assert email_status(has_syntax=True, has_mx=True,
                        mailbox_confirmed=True, catch_all=True) == Status.INFERRED


def test_email_bad_syntax_or_no_mx_is_quarantined():
    assert email_status(has_syntax=False, has_mx=False,
                        mailbox_confirmed=False, catch_all=False) == Status.QUARANTINED
    assert email_status(has_syntax=True, has_mx=False,
                        mailbox_confirmed=False, catch_all=False) == Status.QUARANTINED


# --- S2: route classification (personal vs firm-level) -------------------------
def test_name_matched_localpart_is_personal():
    assert email_route("jane.doe@firm.com", "Jane Doe") == RouteType.PERSONAL
    assert email_route("jdoe@firm.com", "Jane Doe") == RouteType.PERSONAL
    assert email_route("jd@firm.com", "Jane Doe") == RouteType.PERSONAL


def test_generic_mailbox_is_firm_level():
    for addr in ("info@firm.com", "contact@firm.com", "office@firm.com",
                 "family@firm.com", "team@firm.com"):
        assert email_route(addr, "Jane Doe") == RouteType.FIRM_LEVEL


def test_email_naming_a_different_person_is_firm_level():
    # the Stenger error: address names Nick Stenger, listed principal is Julia Foran
    assert email_route("nick.stenger@firm.com", "Julia Foran") == RouteType.FIRM_LEVEL


def test_route_is_firm_level_when_no_principal_name():
    assert email_route("jane.doe@firm.com", "") == RouteType.FIRM_LEVEL


# --- S2: the 200+ hard gate = verified AND personal ---------------------------
def test_personal_gate_needs_both_verified_and_personal():
    assert counts_as_personal_gate(Status.VERIFIED, RouteType.PERSONAL)
    assert not counts_as_personal_gate(Status.INFERRED, RouteType.PERSONAL)
    assert not counts_as_personal_gate(Status.VERIFIED, RouteType.FIRM_LEVEL)


# --- S3: inclusion floor ------------------------------------------------------
def test_inclusion_floor_requires_all_four():
    assert meets_inclusion_floor(FirmCategory.FO_TYPE_UNKNOWN, exists=True,
                                 function_proven=True, entity_coherent=True,
                                 beyond_seed_cells=1)


def test_inclusion_floor_fails_without_beyond_seed_cell():
    assert not meets_inclusion_floor(FirmCategory.SFO, exists=True,
                                     function_proven=True, entity_coherent=True,
                                     beyond_seed_cells=0)


def test_inclusion_floor_fails_for_noncounting_category():
    assert not meets_inclusion_floor(FirmCategory.UNRESOLVED_QUARANTINE, exists=True,
                                     function_proven=True, entity_coherent=True,
                                     beyond_seed_cells=3)


def test_inclusion_floor_fails_without_function_or_coherence():
    assert not meets_inclusion_floor(FirmCategory.MFO, exists=True,
                                     function_proven=False, entity_coherent=True,
                                     beyond_seed_cells=2)
    assert not meets_inclusion_floor(FirmCategory.MFO, exists=True,
                                     function_proven=True, entity_coherent=False,
                                     beyond_seed_cells=2)


# --- S3: commercial standard --------------------------------------------------
def test_commercial_standard_requires_full_bundle():
    assert meets_commercial_standard(has_decision_maker=True,
                                     has_focus_or_mandate=True,
                                     has_reachable_route=True,
                                     has_dated_signal=True)


def test_commercial_standard_fails_missing_any_element():
    assert not meets_commercial_standard(True, True, True, False)
    assert not meets_commercial_standard(True, True, False, True)
    assert not meets_commercial_standard(True, False, True, True)
    assert not meets_commercial_standard(False, True, True, True)
