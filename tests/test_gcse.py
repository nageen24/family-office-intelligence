"""Google Custom Search connector — structured LinkedIn lookup, no scraping.

Queries a CSE restricted to linkedin.com/in for "name" + firm, takes the /in/
profile URL from the JSON, and verifies the slug name-matches the principal. A
match is a personal reach route labeled `inferred` (search-found, not verified by
fetching the profile). Capped at 100 queries/day (free tier); graceful without a key.
"""
from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.ontology import Status, RouteType
from pipeline.enrichment.gcse import (find_person_linkedin, enrich_gcse,
                                      daily_quota_ok, bump_quota, _slug_matches)


class _Stub:
    def __init__(self, urls):
        self.urls = urls
    def search(self, query):
        return self.urls


def test_slug_match_accepts_the_principal_rejects_others():
    assert _slug_matches("https://www.linkedin.com/in/eric-ridenour-cfa", "Eric Ridenour")
    assert not _slug_matches("https://www.linkedin.com/in/bob-smith", "Eric Ridenour")
    assert not _slug_matches("https://www.linkedin.com/company/colony", "Eric Ridenour")


def test_find_returns_matching_profile():
    client = _Stub(["https://www.linkedin.com/company/colony",
                    "https://www.linkedin.com/in/eric-ridenour"])
    assert find_person_linkedin("Eric Ridenour", "Colony", client) == "https://www.linkedin.com/in/eric-ridenour"


def test_find_returns_none_when_no_slug_match():
    client = _Stub(["https://www.linkedin.com/in/someone-else"])
    assert find_person_linkedin("Eric Ridenour", "Colony", client) is None


def test_enrich_sets_personal_inferred_linkedin():
    f = CandidateFirm(firm_name="Colony Family Offices", discovery_source="SEC Form ADV")
    f.principal_name = Cell(value="Eric Ridenour", epistemic=Epistemic.FACT)
    enrich_gcse(f, _Stub(["https://www.linkedin.com/in/eric-ridenour"]))
    assert f.principal_linkedin.value == "https://www.linkedin.com/in/eric-ridenour"
    assert f.principal_linkedin.route is RouteType.PERSONAL
    assert f.principal_linkedin.status is Status.INFERRED     # search-found, not verified


def test_enrich_noop_without_a_principal_name():
    f = CandidateFirm(firm_name="Colony", discovery_source="SEC Form ADV")
    enrich_gcse(f, _Stub(["https://www.linkedin.com/in/eric-ridenour"]))
    assert f.principal_linkedin.is_blank()


def test_daily_quota_caps_at_limit(tmp_path):
    p = str(tmp_path / "quota.json")
    for _ in range(3):
        assert daily_quota_ok(p, limit=3)
        bump_quota(p)
    assert not daily_quota_ok(p, limit=3)                     # 4th call blocked
