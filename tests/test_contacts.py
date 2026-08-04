"""S11 — person-level contacts scraped from the firm's OWN site (scrape-only).

No pattern-guessing (locked decision): candidate emails come only from the firm's
own pages, restricted to its own registrable domain. The principal name is
extracted by an LLM but code-verified to appear on the page. The personal email is
the one whose local-part name-matches the listed principal; generic and
cross-domain addresses are not the principal's personal route.
"""
from pipeline.schema import CandidateFirm
from pipeline.ontology import RouteType, email_route
from pipeline.enrichment.contacts import (same_domain_emails, enrich_contacts,
                                          extract_person_linkedin)

PAGE = ("Our Team. Jane Doe, Managing Partner, leads the firm. "
        "Reach Jane at jane.doe@harborfp.com. General enquiries: info@harborfp.com. "
        "Site by hello@wixpress.com.")


def test_same_domain_emails_filters_cross_domain_and_placeholders():
    got = same_domain_emails(PAGE, "https://harborfp.com")
    assert "jane.doe@harborfp.com" in got
    assert "info@harborfp.com" in got
    assert "hello@wixpress.com" not in got          # vendor / cross-domain dropped


def test_enrich_contacts_sets_principal_and_personal_email():
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"
    llm = lambda page: '{"principal_name": "Jane Doe", "principal_title": "Managing Partner"}'
    enrich_contacts(f, llm=llm, fetch=lambda url: PAGE)
    assert f.principal_name.value == "Jane Doe"
    assert f.principal_email.value == "jane.doe@harborfp.com"   # name-matched, not info@
    assert email_route(f.principal_email.value, f.principal_name.value) is RouteType.PERSONAL


def test_principal_not_on_page_is_rejected():
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"
    # LLM hallucinates a name absent from the page -> code drops it
    llm = lambda page: '{"principal_name": "John Smith", "principal_title": "CEO"}'
    enrich_contacts(f, llm=llm, fetch=lambda url: PAGE)
    assert f.principal_name.is_blank()


def test_extract_person_linkedin_matches_principal_slug():
    text = ("Team. Visit https://www.linkedin.com/in/jane-doe-cfa and the company "
            "page https://www.linkedin.com/company/harbor-fp for more.")
    assert extract_person_linkedin(text, "Jane Doe") == "https://www.linkedin.com/in/jane-doe-cfa"


def test_extract_person_linkedin_ignores_a_different_person():
    text = "See https://www.linkedin.com/in/bob-smith for details."
    assert extract_person_linkedin(text, "Jane Doe") is None


def test_extract_person_linkedin_ignores_company_page():
    text = "Follow us: https://www.linkedin.com/company/jane-doe-partners"
    assert extract_person_linkedin(text, "Jane Doe") is None


def test_enrich_contacts_sets_personal_linkedin_route():
    f = CandidateFirm(firm_name="Harbor Family Partners", discovery_source="SEC Form ADV")
    f.website = "https://harborfp.com"
    page = PAGE + " Jane on LinkedIn: https://www.linkedin.com/in/jane-doe-cfa"
    llm = lambda p: '{"principal_name": "Jane Doe", "principal_title": "Managing Partner"}'
    enrich_contacts(f, llm=llm, fetch=lambda url: page)
    assert f.principal_linkedin.value == "https://www.linkedin.com/in/jane-doe-cfa"
    assert f.principal_linkedin.route is RouteType.PERSONAL


def test_noop_without_website():
    f = CandidateFirm(firm_name="No Site FO", discovery_source="news")
    enrich_contacts(f, llm=lambda p: "{}", fetch=lambda url: PAGE)
    assert f.principal_email.is_blank()
