"""S24 — product language: the 5 states + scope on every answer.

Every response is exactly one of: answered / nothing_found / partial / declined /
error, and always carries its true scope (eligible corpus, matched, shown, and any
constraint that could not be honored). Aggregates run on the full corpus.
"""
from rag.product import respond, STATES


def _search(matched, eligible=100, shown=None, unhonored=None):
    return {"eligible": eligible, "matched": matched, "shown": shown if shown is not None else matched,
            "unhonored": unhonored or [], "hits": [{"firm_name": f"F{i}"} for i in range(matched)]}


def test_answered_state_and_scope():
    r = respond(_search(3, eligible=250))
    assert r["state"] == "answered"
    assert r["scope"]["eligible"] == 250 and r["scope"]["matched"] == 3
    assert "250" in r["scope_line"]


def test_nothing_found_state():
    assert respond(_search(0))["state"] == "nothing_found"


def test_partial_when_a_constraint_is_unhonored():
    r = respond(_search(5, unhonored=["aum_over"]))
    assert r["state"] == "partial"
    assert "aum_over" in r["scope_line"]


def test_declined_when_agent_refuses():
    r = respond({"status": "refused", "findings": [], "goal": "g", "output": None})
    assert r["state"] == "declined"


def test_escalated_maps_to_declined_with_note():
    r = respond({"status": "escalated", "findings": [1, 2], "goal": "g", "output": None})
    assert r["state"] == "declined"
    assert "escalat" in r["scope_line"].lower()


def test_error_state():
    assert respond({"error": "LLM provider down"})["state"] == "error"


def test_every_state_is_one_of_the_five():
    for res in (_search(2), _search(0), _search(1, unhonored=["x"]),
                {"status": "refused", "findings": []}, {"error": "x"}):
        assert respond(res)["state"] in STATES
