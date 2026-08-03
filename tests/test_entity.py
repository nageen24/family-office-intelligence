"""S6 — whole-record entity resolution (the snow-crab defect class, fix#5).

A record must hang together as ONE entity: a value that belongs to a different
entity is quarantined (S5 withhold), not shipped. The canonical example: a
Canadian snow-crab news story attached to DFO Management (Michael Dell's family
office) as recent activity. Coherence is checked against the record's identity
anchors — the firm's distinctive name token(s) and the principal's name parts —
plus email-domain coherence against the firm's own domain.
"""
from pipeline.schema import CandidateFirm, Cell
from pipeline.ontology import Status
from pipeline.validation.entity import (
    distinctive_tokens, signal_coherent, email_domain_coherent, resolve_entity,
)


def _dfo() -> CandidateFirm:
    f = CandidateFirm(firm_name="DFO Management", discovery_source="Wikidata")
    f.principal_name = Cell(value="Michael Dell")
    return f


def test_distinctive_tokens_drop_generic_family_office_words():
    assert distinctive_tokens("Duquesne Family Office") == {"duquesne"}
    assert "dfo" in distinctive_tokens("DFO Management")
    assert "management" not in distinctive_tokens("DFO Management")


def test_signal_coherent_when_it_names_the_firm_or_principal():
    f = _dfo()
    f.recent_signal = Cell(value="DFO Management, Michael Dell's office, buys stake")
    assert signal_coherent(f)


def test_snow_crab_signal_is_incoherent():
    f = _dfo()
    f.recent_signal = Cell(value="Canada boosts snow crab quota for the 2024 season")
    assert not signal_coherent(f)


def test_resolve_entity_quarantines_the_snow_crab_signal():
    f = _dfo()
    f.recent_signal = Cell(value="Canada boosts snow crab quota for the 2024 season",
                           source="https://cbc.ca/snowcrab")
    resolve_entity(f)
    assert f.recent_signal.value is None                      # withheld
    assert f.recent_signal.status is Status.QUARANTINED
    assert "snow crab" in f.recent_signal.quarantined_value   # audit-preserved


def test_resolve_entity_keeps_a_coherent_signal():
    f = _dfo()
    f.recent_signal = Cell(value="Michael Dell's DFO Management hires new CIO")
    resolve_entity(f)
    assert f.recent_signal.value is not None
    assert f.recent_signal.status is not Status.QUARANTINED


def test_email_on_a_different_corporate_domain_is_incoherent():
    f = CandidateFirm(firm_name="Duquesne Family Office", discovery_source="SEC")
    f.website = "https://duquesnefo.com/about"
    f.principal_email = Cell(value="contact@some-other-company.com")
    assert not email_domain_coherent(f)


def test_email_on_the_firm_domain_is_coherent():
    f = CandidateFirm(firm_name="Duquesne Family Office", discovery_source="SEC")
    f.website = "https://duquesnefo.com/about"
    f.principal_email = Cell(value="gc@duquesnefo.com")
    assert email_domain_coherent(f)


def test_resolve_entity_sets_coherent_true_with_an_anchor_false_without():
    anchored = _dfo()
    resolve_entity(anchored)
    assert anchored.entity_coherent is True

    phantom = CandidateFirm(firm_name="Single Family Office", discovery_source="news")
    resolve_entity(phantom)
    assert phantom.entity_coherent is False
