"""Browser layer wiring (use_browser) — website-find for name-only firms.

The Playwright calls themselves are stubbed; this proves the integration: a
name-only firm (no website) gets one via the browser search, verified by a
name-match on the fetched page, then flows through the normal proof pipeline. The
static climb (use_browser=False, add_news=False) never invokes the browser.
"""
from pipeline.schema import CandidateFirm
from pipeline.phase2 import enrich_one_firm

SITE = ("About Cedar Family Office. We are a multi-family office serving families. "
        "Jane Cedar, Managing Partner. https://www.linkedin.com/in/jane-cedar")


class _NoSerper:
    """Disabled Serper stub so these tests isolate the browser/static path."""
    def enabled(self):
        return False


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
    enrich_one_firm(f, _chat, fetch=lambda url: SITE, use_browser=True, add_news=False,
                    serper_client=_NoSerper())
    assert f.website == "https://cedarfo.com"
    assert "multi-family office" in f.proof_function_quote
    assert f.principal_name.value == "Jane Cedar"


def test_browser_rejects_website_that_fails_name_match(monkeypatch):
    import pipeline.enrichment.render as render
    monkeypatch.setattr(render, "find_website", lambda name: "https://wrongco.com")
    # fetched page never mentions 'cedar' -> verification fails -> no website
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="Google News RSS")
    enrich_one_firm(f, _chat, fetch=lambda url: "Unrelated company about page.",
                    use_browser=True, add_news=False, serper_client=_NoSerper())
    assert f.website is None
    assert f.proof_function_quote is None


def test_serper_finds_website_without_the_browser(monkeypatch):
    # the Serper finder works from any IP, so a name-only firm gets a site even
    # with use_browser=False (unlike the CI-blocked browser finder)
    class _Serper:
        def enabled(self):
            return True
        def search(self, q):
            return ["https://cedarfo.com/about"]
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="SEC EDGAR full-text search")
    enrich_one_firm(f, _chat, fetch=lambda url: SITE, use_browser=False,
                    add_news=False, serper_client=_Serper())
    assert f.website == "https://cedarfo.com"
    assert "multi-family office" in f.proof_function_quote


def test_static_climb_without_serper_finds_no_website():
    f = CandidateFirm(firm_name="Cedar Family Office", discovery_source="Google News RSS")
    enrich_one_firm(f, _chat, fetch=lambda url: SITE, use_browser=False,
                    add_news=False, serper_client=_NoSerper())
    assert f.website is None            # no finder active -> stays name-only
