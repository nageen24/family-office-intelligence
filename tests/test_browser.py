"""Browser layer wiring (use_browser) — website-find for name-only firms.

The Playwright calls themselves are stubbed; this proves the integration: a
name-only firm (no website) gets one via the browser search, verified by a
name-match on the fetched page, then flows through the normal proof pipeline. The
static climb (use_browser=False) never invokes the browser.
"""
from pipeline.schema import CandidateFirm
from pipeline.phase2 import enrich_one_firm

SITE = ("About Cedar Family Office. We are a multi-family office serving families. "
        "Jane Cedar, Managing Partner. https://www.linkedin.com/in/jane-cedar")


def _chat(system, user):
    if "principal_name" in system:
        return '{"principal_name": "Jane Cedar", "principal_title": "Managing Partner"}'
    return ('{"is_family_office": true, "function_quote": "We are a multi-family '
            'office serving families", "type": "multi", "type_quote": '
            '"multi-family office serving families", "sec_family_office_exemption": false}')


def test_browser_finds_and_verifies_website_for_name_only_firm(monkeypatch):
    import pipeline.enrichment.render as render
    monkeypatch.setattr(render, "find_website", lambda name: "https://cedarfo.com")
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="Google News RSS")
    enrich_one_firm(f, _chat, fetch=lambda url: SITE, use_browser=True)
    assert f.website == "https://cedarfo.com"
    assert "multi-family office" in f.proof_function_quote
    assert f.principal_name.value == "Jane Cedar"


def test_browser_rejects_website_that_fails_name_match(monkeypatch):
    import pipeline.enrichment.render as render
    monkeypatch.setattr(render, "find_website", lambda name: "https://wrongco.com")
    # fetched page never mentions 'cedar' -> verification fails -> no website
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="Google News RSS")
    enrich_one_firm(f, _chat, fetch=lambda url: "Unrelated company about page.",
                    use_browser=True)
    assert f.website is None
    assert f.proof_function_quote is None


def test_static_climb_does_not_find_websites():
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="Google News RSS")
    enrich_one_firm(f, _chat, fetch=lambda url: SITE, use_browser=False)
    assert f.website is None            # name-only firm stays unqualifiable statically
