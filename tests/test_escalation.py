"""Escalation queue — when the agent may not decide, a human does.

An ambiguous/unsafe case is written to needs_human.json and the agent stops there.
A human decision is applied and the record marked 'human-authorized' in the log —
the worker never self-authorizes an escalated case.
"""
from rag.escalation import open_case, pending_cases, resolve_case


def test_open_case_writes_a_pending_case(tmp_path):
    p = str(tmp_path / "needs_human.json")
    cid = open_case("ambiguous SFO/MFO", {"firm": "Acme"}, options=["SFO", "MFO"],
                    path=p, log=str(tmp_path / "log"))
    cases = pending_cases(p)
    assert len(cases) == 1 and cases[0]["id"] == cid
    assert cases[0]["reason"] == "ambiguous SFO/MFO"
    assert cases[0]["status"] == "pending"


def test_resolve_marks_human_authorized(tmp_path):
    p, lg = str(tmp_path / "needs_human.json"), str(tmp_path / "log")
    cid = open_case("conflicting sources", {"firm": "Beta"}, path=p, log=lg)
    resolved = resolve_case(cid, decision="treat as MFO", path=p, log=lg)
    assert resolved["status"] == "resolved"
    assert resolved["authorization"] == "human-authorized"
    assert resolved["decision"] == "treat as MFO"
    assert pending_cases(p) == []                     # no longer pending
    assert "human-authorized" in open(lg, encoding="utf-8").read()


def test_resolve_unknown_case_returns_none(tmp_path):
    p = str(tmp_path / "needs_human.json")
    assert resolve_case("nope", "x", path=p, log=str(tmp_path / "log")) is None
