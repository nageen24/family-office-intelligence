"""Apollo contact enrichment — a provider source with OUR validation + honest labels.

Apollo enters like any source: its returned profile must match the named person AND
the current firm before we trust it, and everything it returns is labeled
`inferred` (provider-returned), NEVER `verified`. LinkedIn is fetched first (it
recovers the personal-reach gate for free credits); email is revealed only on the
strongest records (scarce free-tier email credits). An Apollo email is a reach
route but counts toward the 200 VERIFIED emails only if it also passes our own SMTP
check later.
"""
from pipeline.schema import CandidateFirm, Cell, Epistemic
from pipeline.ontology import Status, RouteType
from pipeline.enrichment.apollo import validate_person, enrich_apollo, is_strong

PERSON = {"first_name": "Eric", "last_name": "Ridenour", "name": "Eric Ridenour",
          "title": "Managing Partner",
          "linkedin_url": "https://www.linkedin.com/in/eric-ridenour",
          "email": "eric@colonyfamilyoffices.com",
          "organization": {"name": "Colony Family Offices", "primary_domain": "colonyfamilyoffices.com"}}


def _firm(name="Colony Family Offices", principal="Eric Ridenour", website="https://colonyfamilyoffices.com"):
    f = CandidateFirm(firm_name=name, discovery_source="SEC Form ADV")
    f.website = website
    if principal:
        f.principal_name = Cell(value=principal, epistemic=Epistemic.FACT)
    f.proof_function_quote = "we operate as a multi-family office"
    return f


def _client(person):
    return lambda kind, **params: person


def test_validate_requires_name_and_firm_match():
    assert validate_person(PERSON, "Eric Ridenour", "Colony Family Offices")


def test_validate_rejects_a_different_person():
    assert not validate_person(PERSON, "Jane Smith", "Colony Family Offices")


def test_validate_rejects_a_different_firm():
    assert not validate_person(PERSON, "Eric Ridenour", "Riverglades Family Offices")


def test_linkedin_is_set_personal_but_inferred_not_verified():
    f = _firm()
    enrich_apollo(f, _client(PERSON), reveal_email=False)
    assert f.principal_linkedin.value == "https://www.linkedin.com/in/eric-ridenour"
    assert f.principal_linkedin.route is RouteType.PERSONAL
    assert f.principal_linkedin.status is Status.INFERRED     # provider-returned != verified
    assert f.principal_email.is_blank()                       # no email without reveal


def test_email_revealed_is_provider_returned_inferred():
    f = _firm()
    enrich_apollo(f, _client(PERSON), reveal_email=True)
    assert f.principal_email.value == "eric@colonyfamilyoffices.com"
    assert f.principal_email.route is RouteType.PERSONAL
    assert f.principal_email.status is Status.INFERRED        # NOT verified (no SMTP yet)
    assert "not" in (f.principal_email.method or "").lower() and "verif" in (f.principal_email.method or "").lower()


def test_mismatched_profile_sets_nothing():
    f = _firm(name="Riverglades Family Offices")              # Apollo returns a Colony person
    enrich_apollo(f, _client(PERSON), reveal_email=True)
    assert f.principal_linkedin.is_blank() and f.principal_email.is_blank()


def test_unnamed_firm_recovers_principal_from_apollo():
    f = _firm(principal=None)                                 # we had no principal
    enrich_apollo(f, _client(PERSON), reveal_email=False)
    assert f.principal_name.value == "Eric Ridenour"
    assert f.principal_name.status is Status.INFERRED
    assert f.principal_linkedin.route is RouteType.PERSONAL


def test_apollo_pass_recovers_reach_and_conserves_email_credits():
    from pipeline.climb import _apollo_pass
    from pipeline.validation.validate import _has_personal_reach
    thin = _firm()                                  # function-proven, no reach, not strong
    assert not _has_personal_reach(thin)
    n = _apollo_pass([thin], email_budget=0, client=_client(PERSON))
    assert n == 1
    assert _has_personal_reach(thin)                # LinkedIn recovered the reach gate
    assert thin.principal_email.is_blank()          # not strong + budget 0 -> no email credit spent


def test_is_strong_only_for_rich_records():
    strong = _firm()
    strong.investing_thesis = Cell(value="healthcare buyouts")
    strong.recent_signal = Cell(value="acquired X", asof_date="2026-07")
    assert is_strong(strong)
    assert not is_strong(_firm())                             # no focus / no signal
