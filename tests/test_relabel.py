"""S7 — relabel every value to its narrowest accurate label (fix#4, #6).

Firm level: classify_category outputs the 5-category ontology under STRICT
Proof B (own filing/exemption only). 13F-name / press / registry no longer prove
function, so a firm known only that way is Unresolved-Quarantine.

Cell level: narrow_status assigns the S2 status word. Authoritative primary
source = verified; derived/indirect = inferred; blank = unresolved; a failed or
cross-entity value stays quarantined. Contact cells also get a route.
"""
from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.ontology import FirmCategory, Status, RouteType
from pipeline.validation.relabel import (
    classify_category, narrow_status, phone_route, relabel_record,
)


def _fo(**kw) -> CandidateFirm:
    f = CandidateFirm(firm_name="Doe Family Office", discovery_source="SEC EDGAR")
    for k, v in kw.items():
        setattr(f, k, v)
    return f


# --- classify_category (strict Proof B) ---------------------------------------
def test_sec_family_office_exemption_is_sfo():
    f = _fo(sec_family_office_exemption=True)
    cat, _ = classify_category(f)
    assert cat is FirmCategory.SFO           # the exemption is single-family by definition


def test_own_source_multifamily_statement_is_mfo():
    f = _fo(proof_function_quote="Acme operates as a family office",
            proof_type_quote="a multi-family office serving multiple families")
    cat, _ = classify_category(f)
    assert cat is FirmCategory.MFO


def test_function_proven_but_type_unknown():
    f = _fo(proof_function_quote="We operate as a family office for our clients")
    cat, _ = classify_category(f)
    assert cat is FirmCategory.FO_TYPE_UNKNOWN


def test_name_or_13f_only_is_quarantined():
    f = _fo(type_evidence="13F filed under a family-office name (CIK 123)")
    cat, _ = classify_category(f)
    assert cat is FirmCategory.UNRESOLVED_QUARANTINE


def test_adviser_evidence_without_function_is_ria_nonqualifying():
    f = _fo(ria_adviser_evidence="Form ADV: general wealth-management to clients")
    cat, _ = classify_category(f)
    assert cat is FirmCategory.RIA_NONQUALIFYING


# --- narrow_status ------------------------------------------------------------
def test_authoritative_fact_is_verified():
    c = Cell(value="212-830-6500", source="SEC filing", epistemic=Epistemic.FACT)
    narrow_status(c)
    assert c.status is Status.VERIFIED


def test_derived_figure_is_inferred_even_if_marked_fact():
    c = Cell(value="$3.38B (13F portfolio value)", source="13F",
             epistemic=Epistemic.FACT)
    narrow_status(c, derived=True)
    assert c.status is Status.INFERRED


def test_blank_is_unresolved():
    c = Cell()
    narrow_status(c)
    assert c.status is Status.UNRESOLVED


def test_quarantined_stays_quarantined():
    c = Cell(value="x", epistemic=Epistemic.FACT)
    c.quarantine("cross-entity")
    narrow_status(c)
    assert c.status is Status.QUARANTINED


# --- routes -------------------------------------------------------------------
def test_phone_from_filing_is_firm_level_direct_line_is_personal():
    assert phone_route(Cell(value="212-830-6500", method="from SEC filing")) == RouteType.FIRM_LEVEL
    assert phone_route(Cell(value="917-555-1212", method="principal's direct mobile")) == RouteType.PERSONAL


def test_relabel_record_sets_category_and_routes_and_narrows_aum():
    f = _fo(sec_family_office_exemption=True)
    f.principal_name = Cell(value="Jane Doe", epistemic=Epistemic.FACT, source="ADV")
    f.principal_email = Cell(value="jane.doe@firm.com", status=Status.VERIFIED)
    f.aum = Cell(value="$1B (13F portfolio value)", epistemic=Epistemic.FACT)
    relabel_record(f)
    assert f.category is FirmCategory.SFO
    assert f.principal_email.route is RouteType.PERSONAL
    assert f.aum.status is Status.INFERRED          # computed figure never verified
    assert f.principal_name.status is Status.VERIFIED
