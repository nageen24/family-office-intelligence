"""S9 — SEC Form ADV roster discovery (the Phase-2 backbone source).

The registered-adviser roster gives, per firm, its OWN website + phone + address
+ CRD/CIK (existence + reachability + the site S10 needs to prove FO-function).
We take a broad-but-bounded net: advisers that serve high-net-worth individuals
(Item 5.D(b)) and, by default, are concentrated on individuals (no institutional
clients) with a real own website — the functional MFO/FO proxy. Registration is
NOT function proof; category stays Unresolved-Quarantine until S10 verifies the
firm's own site.
"""
from pipeline.discovery.sec_adv import select_rows, candidate_from_row
from pipeline.schema import CandidateFirm


def _row(**kw):
    base = {
        "Primary Business Name": "ACME FAMILY OFFICE", "Legal Name": "ACME FO LLC",
        "Website Address": "http://www.acme.com/about",
        "Main Office City": "NEWPORT BEACH", "Main Office State": "CA",
        "Main Office Telephone Number": "949-555-1000",
        "CIK#": "0001234567", "Organization CRD#": "123456",
        "Latest ADV Filing Date": "03/31/2026",
        "5D(b)(1)": "3",  # 3 HNW-individual clients
        "5D(d)(1)": "", "5D(f)(1)": "", "5D(g)(1)": "", "5D(k)(1)": "", "5D(l)(1)": "",
    }
    base.update(kw)
    return base


def test_select_keeps_hnw_concentrated_with_site():
    rows = [_row()]
    assert len(select_rows(rows)) == 1


def test_select_drops_row_without_real_website():
    assert select_rows([_row(**{"Website Address": ""})]) == []
    assert select_rows([_row(**{"Website Address": "https://linkedin.com/company/x"})]) == []


def test_select_drops_row_that_serves_no_hnw():
    assert select_rows([_row(**{"5D(b)(1)": ""})]) == []


def test_concentrated_default_drops_institutional_but_wide_keeps_it():
    inst = _row(**{"5D(f)(1)": "10"})   # also has pooled-vehicle (institutional) clients
    assert select_rows([inst]) == []                    # default concentrated=True
    assert len(select_rows([inst], concentrated=False)) == 1


def test_candidate_mapping():
    c = candidate_from_row(_row())
    assert isinstance(c, CandidateFirm)
    assert c.firm_name == "ACME FAMILY OFFICE"
    assert c.website == "http://www.acme.com"           # normalized to scheme://host
    assert c.hq_location == "NEWPORT BEACH, CA"
    assert c.cik == "0001234567"
    assert c.principal_phone.value == "949-555-1000"
    assert "SEC Form ADV" in c.discovery_source
    assert "123456" in (c.proof_exists or "")           # CRD recorded as existence proof
    # discovery must NOT assert function — that's S10's job
    assert c.proof_function_quote is None
