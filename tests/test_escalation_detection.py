"""Climb-side escalation detection: ambiguous records are parked as Review and
opened as real cases in the existing needs_human queue — never decided."""
import json

from pipeline.escalation import escalate_ambiguous, type_conflict, entity_conflict
from pipeline.schema import CandidateFirm
from rag.escalation import pending_cases, resolve_case


def _proven(name="Ambiguous FO"):
    f = CandidateFirm(firm_name=name, discovery_source="test")
    f.website = "https://ambiguous.com"
    f.proof_function_quote = "We operate as a family office."
    f.record_status = "Qualified"
    return f


def test_both_type_markers_is_a_conflict():
    f = _proven()
    f.proof_type_quote = ("Founded as a single family office, we now serve "
                          "multiple families.")
    assert "both" in type_conflict(f)


def test_exemption_vs_multi_statement_is_a_conflict():
    f = _proven()
    f.sec_family_office_exemption = True
    f.proof_type_quote = "We are a multi-family office."
    assert "exemption" in type_conflict(f)


def test_entity_mismatch_only_on_proven_firms():
    f = _proven()
    f.entity_coherent = False
    assert "entity mismatch" in entity_conflict(f)
    bare = CandidateFirm(firm_name="No proof", discovery_source="t")
    bare.entity_coherent = False
    assert entity_conflict(bare) is None


def test_conflict_parks_record_and_opens_pending_case(tmp_path):
    p, lg = str(tmp_path / "needs_human.json"), str(tmp_path / "log")
    f = _proven()
    f.sec_family_office_exemption = True
    f.proof_type_quote = "We are a multi-family office."
    assert escalate_ambiguous([f], path=p, log=lg) == 1
    assert f.record_status == "Review"            # ships on no customer surface
    cases = pending_cases(p)
    assert len(cases) == 1 and "exemption" in cases[0]["reason"]
    assert cases[0]["context"]["proof_type_quote"] == f.proof_type_quote
    assert cases[0]["options"] == ["SFO", "MFO", "FO-type-unknown", "Reject"]


def test_one_case_per_firm_and_pending_stays_parked(tmp_path):
    p, lg = str(tmp_path / "needs_human.json"), str(tmp_path / "log")
    f = _proven()
    f.entity_coherent = False
    escalate_ambiguous([f], path=p, log=lg)
    f.record_status = "Qualified"                 # a re-validation re-decided it
    escalate_ambiguous([f], path=p, log=lg)       # later run re-detects
    assert len(json.load(open(p))) == 1           # still one case
    assert f.record_status == "Review"            # and it stays parked


def test_human_resolution_is_respected_not_reparked(tmp_path):
    p, lg = str(tmp_path / "needs_human.json"), str(tmp_path / "log")
    f = _proven()
    f.entity_coherent = False
    escalate_ambiguous([f], path=p, log=lg)
    cid = pending_cases(p)[0]["id"]
    resolve_case(cid, decision="confirm identity + qualify", path=p, log=lg)
    f.record_status = "Qualified"
    escalate_ambiguous([f], path=p, log=lg)       # next run
    assert f.record_status == "Qualified"         # human ruled; not re-parked
    assert pending_cases(p) == []


def test_unambiguous_records_are_untouched(tmp_path):
    p, lg = str(tmp_path / "needs_human.json"), str(tmp_path / "log")
    f = _proven()
    f.proof_type_quote = "We serve one family."
    assert escalate_ambiguous([f], path=p, log=lg) == 0
    assert f.record_status == "Qualified"
