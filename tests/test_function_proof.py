"""S10 — enrichment-beyond-seed: capture a code-verified FO-function proof.

The S1 mechanism made real: an LLM reads the firm's OWN website and quotes the
exact sentence proving it operates as a family office (Proof B) and its type
(Proof C). CODE then verifies each quote literally exists on the page
(quote_present) — a hallucinated or paraphrased quote is rejected, so the control
lives in code, not in trust of the model.
"""
from pipeline.enrichment.function_proof import extract_function_proof, enrich_function
from pipeline.schema import CandidateFirm

PAGE = ("About Us. Harbor Family Partners is a multi-family office serving 40 "
        "families across three generations. We provide integrated wealth "
        "management for our client families.")


def _stub(payload):
    """Return an llm callable that yields a fixed JSON string regardless of input."""
    import json
    return lambda _text: json.dumps(payload)


def test_verified_function_and_type_quotes_are_kept():
    llm = _stub({
        "is_family_office": True,
        "function_quote": "Harbor Family Partners is a multi-family office serving 40 families",
        "type": "multi",
        "type_quote": "multi-family office serving 40 families",
        "sec_family_office_exemption": False,
    })
    proof = extract_function_proof(PAGE, llm)
    assert proof["function_quote"].startswith("Harbor Family Partners is a multi-family office")
    assert proof["type_quote"] == "multi-family office serving 40 families"


def test_hallucinated_quote_is_rejected_by_code():
    # the model claims a sentence that is NOT on the page -> control drops it
    llm = _stub({
        "is_family_office": True,
        "function_quote": "We are the single family office of the Rockefeller family",
        "type": "single",
        "type_quote": "single family office of the Rockefeller family",
        "sec_family_office_exemption": False,
    })
    proof = extract_function_proof(PAGE, llm)
    assert proof["function_quote"] is None
    assert proof["type_quote"] is None


def test_not_a_family_office_yields_no_proof():
    llm = _stub({"is_family_office": False, "function_quote": "",
                 "type": "unknown", "type_quote": "", "sec_family_office_exemption": False})
    proof = extract_function_proof(PAGE, llm)
    assert proof["function_quote"] is None


def test_exemption_flag_passes_through_when_function_proven():
    llm = _stub({
        "is_family_office": True,
        "function_quote": "integrated wealth management for our client families",
        "type": "unknown", "type_quote": "",
        "sec_family_office_exemption": True,
    })
    proof = extract_function_proof(PAGE, llm)
    assert proof["sec_family_office_exemption"] is True


def test_enrich_function_sets_proof_fields_from_own_site():
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"
    llm = _stub({
        "is_family_office": True,
        "function_quote": "Harbor Family Partners is a multi-family office serving 40 families",
        "type": "multi",
        "type_quote": "multi-family office serving 40 families",
        "sec_family_office_exemption": False,
    })
    enrich_function(f, llm=llm, fetch=lambda url: PAGE)
    assert f.proof_function_source == "https://harborfp.com"
    assert "multi-family office" in f.proof_function_quote
    assert f.proof_type_quote == "multi-family office serving 40 families"


def test_enrich_function_noops_without_a_website():
    f = CandidateFirm(firm_name="No Site FO", discovery_source="news")
    enrich_function(f, llm=_stub({}), fetch=lambda url: PAGE)
    assert f.proof_function_quote is None
