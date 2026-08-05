"""S13 — per-firm beyond-seed enrichment: one site fetch, both proofs.

enrich_one_firm fetches the firm's own site ONCE and runs both the function-proof
extractor (Proof B/C) and the contact extractor (principal + personal email) on
the same text, using the 2-arg LLM client (system+user).
"""
from pipeline.schema import CandidateFirm
from pipeline.ontology import FirmCategory, RouteType
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


# The homepage proves function but names no one; the /team page carries the person.
HOME = ("Acme Family Office. We operate as a single-family office serving one "
        "family. See our team page for the people behind the firm.")
TEAM = ("Our Team. John Smith, Founder and CEO. Reach him at john.smith@acme.com. "
        "Profile: https://www.linkedin.com/in/john-smith")


def _chat_name_only_on_team(system, user):
    if "principal_name" in system:
        # a name is present only in the /team text, not on the homepage
        if "John Smith" in user:
            return '{"principal_name": "John Smith", "principal_title": "Founder and CEO"}'
        return '{"principal_name": "", "principal_title": ""}'
    return ('{"is_family_office": true, "function_quote": "We operate as a '
            'single-family office serving one family", "type": "single", '
            '"type_quote": "single-family office serving one family", '
            '"sec_family_office_exemption": false}')


def test_principal_recovered_from_people_page_when_homepage_has_no_name():
    primary, people = {"n": 0}, {"n": 0}
    def fetch(url):
        primary["n"] += 1
        return HOME
    def people_fetch(url):
        people["n"] += 1
        return TEAM
    f = CandidateFirm(firm_name="Acme Family Office", discovery_source="SEC Form ADV")
    f.website = "https://acme.com"

    enrich_one_firm(f, _chat_name_only_on_team, fetch=fetch, people_fetch=people_fetch)

    assert f.proof_function_quote                      # function proven from homepage
    assert primary["n"] == 1 and people["n"] == 1      # people page fetched exactly once
    assert f.principal_name.value == "John Smith"      # name recovered from /team
    assert f.principal_email.value == "john.smith@acme.com"
    assert "john-smith" in f.principal_linkedin.value  # personal LinkedIn from /team
    assert f.principal_linkedin.route is RouteType.PERSONAL


def test_people_fallback_not_used_when_homepage_already_names_the_principal():
    people = {"n": 0}
    def people_fetch(url):
        people["n"] += 1
        return TEAM
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"
    enrich_one_firm(f, _chat2, fetch=lambda u: PAGE, people_fetch=people_fetch)
    assert f.principal_name.value == "Jane Doe"
    assert people["n"] == 0                            # no extra fetch on the common path
