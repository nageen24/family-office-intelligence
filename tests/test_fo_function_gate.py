"""Tightened FO-function gate: a quote proves function only if the firm states it
IS / operates AS a family office — not that it serves families or lists services."""
from pipeline.ontology import establishes_fo_function
from pipeline.enrichment.function_proof import extract_function_proof


def test_identity_statements_qualify():
    for q in [
        "We are a single-family office serving one family.",
        "The firm operates as a multi-family office.",
        "AC Family Office is an outsourced family office with 250 years experience.",
        "Established in 1998, it operates as a single family office.",
        "The company functions as a multi family office for five families.",
        # adjectives + comma between the article and the phrase must still pass
        "Colony Family Offices is an independent, multi-family office providing advice.",
        "Cambient Family Office is an independent multi-family office serving families.",
        # bare predicate (no copula) — a tagline that IS an identity statement
        "An Independent Multi-Family Office and Wealth Management Firm",
        # 'as a ... , we provide ...' — a trailing serving clause must NOT disqualify
        "As a discreet and exclusive multi-family office, we provide high-touch service.",
        "As a family office, we advise on and coordinate just about everything.",
        "An independent family office coordinating every part of a family's life.",
    ]:
        assert establishes_fo_function(q), q


def test_serving_families_or_service_line_do_not_qualify():
    for q in [
        "Campbell Capital is a family-owned, multi-generational Registered Investment Advisor.",
        "founded in 1992 to serve high net worth individuals, families, and trusts",
        "financial portfolio management for high-net-worth individuals and families",
        "Family Office Services With experts guiding your family wealth management",
        "fee for service RIA primarily serving individuals and family foundations",
        "We manage portfolios for institutions, families, and individual investors",
        "We Serve as the Chief Financial Officer to Families.",
        "Eagle Bay Family Office delivers comprehensive family office services for wealthy families",
        # serving OTHER family offices (plural object), not being one
        "The firm is a leading advisor to family offices and individuals.",
        "Borrowing lessons from successful family offices, it took time to build.",
        # 'family office' only as the head of a services menu, not an identity
        "We offer a full family office services platform to our clients.",
        # comparison — providing what is 'reserved FOR a family office', not being one
        "oversight and execution typically reserved for a private family office",
        # the phrase is the firm's NAME (subject), predicate is a different noun
        "The Innovative Family Office is a private wealth management advisory firm.",
    ]:
        assert not establishes_fo_function(q), q


def test_extract_rejects_valid_onpage_quote_that_is_not_identity():
    page = "We proudly serve high-net-worth individuals and families across the US."
    llm = lambda t: ('{"is_family_office": true, "function_quote": "We proudly serve '
                     'high-net-worth individuals and families across the US.", '
                     '"type": "unknown", "type_quote": "", "sec_family_office_exemption": false}')
    proof = extract_function_proof(page, llm)
    assert proof["function_quote"] is None
    assert proof["no_proof_reason"] == "not-fo-identity-statement"


def test_extract_accepts_true_identity_quote():
    page = "Cedar LLC operates as a multi-family office for a dozen families."
    llm = lambda t: ('{"is_family_office": true, "function_quote": "Cedar LLC operates '
                     'as a multi-family office for a dozen families.", "type": "multi", '
                     '"type_quote": "", "sec_family_office_exemption": false}')
    proof = extract_function_proof(page, llm)
    assert proof["function_quote"] and proof["no_proof_reason"] is None
