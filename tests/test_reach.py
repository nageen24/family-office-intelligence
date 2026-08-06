"""Free reach recovery: principal from team page, Serper LinkedIn, direct phone."""
from pipeline.enrichment.reach import recover_reach, _direct_phone
from pipeline.schema import CandidateFirm, Cell
from pipeline.ontology import RouteType


class _Serper:
    def __init__(self, li=None):
        self.li = li
    def enabled(self):
        return True
    def search(self, q):
        return [self.li] if self.li else []


def _chat(system, user):
    return '{"principal_name": "Eric Ridenour", "principal_title": "Managing Partner"}'


def test_direct_phone_only_when_labelled():
    assert _direct_phone("Direct: 704-285-7300") == "704-285-7300"
    assert _direct_phone("Mobile 212 885 4200") == "212 885 4200"
    assert _direct_phone("Main office: 704-285-7300") is None   # firm-level, not personal


def test_recovers_name_and_linkedin(monkeypatch):
    f = CandidateFirm(firm_name="Colony Family Offices", discovery_source="SEC Form ADV")
    f.website = "https://colony.com"
    li = "https://www.linkedin.com/in/eric-ridenour-123"
    recover_reach(f, _chat, serper=_Serper(li),
                  people_fetch=lambda u: "Our team: Eric Ridenour, Managing Partner.",
                  site_fetch=lambda u: "")
    assert f.principal_name.value == "Eric Ridenour"
    assert f.principal_linkedin.value == li
    assert f.principal_linkedin.route is RouteType.PERSONAL


def test_drops_firm_name_echoed_as_principal(monkeypatch):
    f = CandidateFirm(firm_name="Tillman Hartley LLC", discovery_source="SEC Form ADV")
    f.website = "https://th.com"
    f.principal_name = Cell(value="Tillman Hartley")     # the firm name, not a person
    # team page has no real person; no LinkedIn found
    recover_reach(f, lambda s, u: '{"principal_name": "", "principal_title": ""}',
                  serper=_Serper(None),
                  people_fetch=lambda u: "We are an independent multi-family office.",
                  site_fetch=lambda u: "")
    assert f.principal_name.is_blank()                   # bad value cleared, none found
    assert f.principal_linkedin.is_blank()


def test_direct_phone_becomes_personal_route():
    f = CandidateFirm(firm_name="Acme Family Office", discovery_source="SEC Form ADV")
    f.website = "https://acme.com"
    recover_reach(f, lambda s, u: '{"principal_name": "", "principal_title": ""}',
                  serper=_Serper(None),
                  people_fetch=lambda u: "Jane Doe, Partner. Direct: 305-555-1212",
                  site_fetch=lambda u: "")
    assert f.principal_phone.value == "305-555-1212"
    assert f.principal_phone.route is RouteType.PERSONAL
