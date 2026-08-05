"""Hunter/Snov provider emails: never pattern-built, our validation gates, honest
labels, and a committed monthly spend guard."""
import json

from pipeline.enrichment.email_finder import (
    enrich_hunter, enrich_snov, enrich_email_finders,
    monthly_quota_ok, bump_quota)
from pipeline.ontology import Status, RouteType
from pipeline.schema import CandidateFirm, Cell


def _firm(email_cell=None):
    f = CandidateFirm(firm_name="Sample Family Office", discovery_source="test")
    f.website = "https://www.samplefo.com"
    f.proof_function_quote = "We are a family office."
    f.principal_name = Cell(value="Jane Doe")
    if email_cell:
        f.principal_email = email_cell
    return f


class _Hunter:
    def __init__(self, data):
        self.data = data
    def enabled(self):
        return True
    def find(self, domain, first_name, last_name):
        return self.data


class _Snov:
    def __init__(self, emails):
        self.emails = emails
    def enabled(self):
        return True
    def find(self, domain, first_name, last_name):
        return self.emails


def test_hunter_source_backed_email_lands_as_inferred_personal():
    f = _firm()
    ok = enrich_hunter(f, _Hunter({"email": "jane.doe@samplefo.com", "score": 92,
                                   "sources": [{"uri": "x"}],
                                   "verification": {"status": "unknown"}}))
    assert ok
    assert f.principal_email.value == "jane.doe@samplefo.com"
    assert f.principal_email.status is Status.INFERRED       # never self-certified
    assert f.principal_email.route is RouteType.PERSONAL
    assert "NOT mailbox-verified" in f.principal_email.method


def test_hunter_pattern_guess_without_sources_is_refused():
    f = _firm()
    ok = enrich_hunter(f, _Hunter({"email": "jane.doe@samplefo.com", "score": 72,
                                   "sources": [],
                                   "verification": {"status": "unknown"}}))
    assert not ok and f.principal_email.is_blank()


def test_hunter_verified_but_sourceless_is_accepted():
    f = _firm()
    ok = enrich_hunter(f, _Hunter({"email": "jane.doe@samplefo.com", "score": 88,
                                   "sources": [],
                                   "verification": {"status": "valid"}}))
    assert ok and "valid" in f.principal_email.method


def test_wrong_domain_and_generic_mailbox_are_refused():
    f = _firm()
    assert not enrich_hunter(f, _Hunter({"email": "jane.doe@otherfirm.com",
                                         "sources": [{"uri": "x"}],
                                         "verification": {"status": "valid"}}))
    assert not enrich_hunter(f, _Hunter({"email": "info@samplefo.com",
                                         "sources": [{"uri": "x"}],
                                         "verification": {"status": "valid"}}))
    assert f.principal_email.is_blank()


def test_snov_accepts_only_valid_status():
    f = _firm()
    assert not enrich_snov(f, _Snov([{"email": "jane.doe@samplefo.com",
                                      "emailStatus": "unknown"}]))
    assert enrich_snov(f, _Snov([{"email": "jane.doe@samplefo.com",
                                  "emailStatus": "valid"}]))
    assert f.principal_email.status is Status.INFERRED


def test_existing_email_is_never_overwritten():
    f = _firm(email_cell=Cell(value="jane@samplefo.com"))
    changed = enrich_email_finders(
        f, _Hunter({"email": "jane.doe@samplefo.com",
                    "sources": [{"uri": "x"}],
                    "verification": {"status": "valid"}}),
        _Snov([]))
    assert not changed and f.principal_email.value == "jane@samplefo.com"


def test_monthly_quota_caps_and_resets(tmp_path):
    path = str(tmp_path / "email_quota.json")
    assert monthly_quota_ok("hunter", limit=2, path=path)
    bump_quota("hunter", path)
    bump_quota("hunter", path)
    assert not monthly_quota_ok("hunter", limit=2, path=path)
    assert monthly_quota_ok("snov", limit=2, path=path)      # per-provider counters
    # a stale month resets
    q = json.load(open(path))
    q["month"] = "2020-01"
    json.dump(q, open(path, "w"))
    assert monthly_quota_ok("hunter", limit=2, path=path)
