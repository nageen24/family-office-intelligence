"""Serper website-finder for name-only firms + person-name guard."""
from pipeline.enrichment.serper import find_company_website
from pipeline.enrichment.contacts import extract_principal, _looks_like_person


class _Client:
    def __init__(self, urls):
        self.urls = urls
    def enabled(self):
        return True
    def search(self, q):
        return self.urls


def test_returns_first_real_firm_domain():
    c = _Client(["https://whalewisdom.com/x", "https://pathstone.com/about",
                 "https://www.linkedin.com/company/y"])
    assert find_company_website("Pathstone", c) == "https://pathstone.com"


def test_skips_all_aggregators_and_registries():
    c = _Client(["https://pitchbook.com/p", "https://sec.gov/x",
                 "https://brokercheck.finra.org/z", "https://www.propublica.org/n"])
    assert find_company_website("Some Firm", c) is None


def test_empty_name_returns_none():
    assert find_company_website("", _Client(["https://x.com"])) is None


def test_person_guard_rejects_firm_name_as_principal():
    # 'Wilshire' extracted for 'Wilshire Private Markets Family Office' is the firm
    assert not _looks_like_person("Wilshire", "Wilshire Private Markets Family Office")
    assert not _looks_like_person("Family Office", "ACME Family Office")   # <2 person tokens after firm overlap
    assert _looks_like_person("Michael Nelson", "Eagle Bay Family Office")  # a real person


def test_extract_principal_drops_firm_echo():
    page = "Wilshire Private Markets Family Office Fund provides capital."
    llm = lambda t: '{"principal_name": "Wilshire", "principal_title": ""}'
    assert extract_principal(page, llm, firm_name="Wilshire Private Markets Family Office") is None
    # a real person on the page still passes
    page2 = "Our founder Jane Cedar leads the office."
    llm2 = lambda t: '{"principal_name": "Jane Cedar", "principal_title": "Founder"}'
    got = extract_principal(page2, llm2, firm_name="Cedar Family Office")
    assert got and got["name"] == "Jane Cedar"
