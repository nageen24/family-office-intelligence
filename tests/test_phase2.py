"""S13 — per-firm beyond-seed enrichment: one site fetch, both proofs.

enrich_one_firm fetches the firm's own site ONCE and runs both the function-proof
extractor (Proof B/C) and the contact extractor (principal + personal email) on
the same text, using the 2-arg LLM client (system+user).
"""
from pipeline.schema import CandidateFirm
from pipeline.ontology import FirmCategory
from pipeline.phase2 import enrich_one_firm
from pipeline.validation.relabel import classify_category

PAGE = ("About Harbor Family Partners. We are a multi-family office serving 40 "
        "families. Jane Doe, Managing Partner. Contact jane.doe@harborfp.com.")


def _chat2(system, user):
    # the two calls are told apart by their system prompt
    if "principal_name" in system:
        return '{"principal_name": "Jane Doe", "principal_title": "Managing Partner"}'
    return ('{"is_family_office": true, '
            '"function_quote": "We are a multi-family office serving 40 families", '
            '"type": "multi", "type_quote": "multi-family office serving 40 families", '
            '"sec_family_office_exemption": false}')


def test_enrich_one_firm_captures_function_and_contact_from_one_fetch():
    fetched = {"n": 0}
    def fetch(url):
        fetched["n"] += 1
        return PAGE
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"

    enrich_one_firm(f, _chat2, fetch=fetch)

    assert fetched["n"] == 1                                  # ONE fetch, reused
    assert "multi-family office" in f.proof_function_quote
    assert f.principal_name.value == "Jane Doe"
    assert f.principal_email.value == "jane.doe@harborfp.com"
    assert classify_category(f)[0] is FirmCategory.MFO


def test_enrich_one_firm_noop_without_site():
    f = CandidateFirm(firm_name="No Site", discovery_source="news")
    enrich_one_firm(f, _chat2, fetch=lambda u: PAGE)
    assert f.proof_function_quote is None
