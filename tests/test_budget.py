"""Budget guard — a per-run cost ledger; the agent refuses to continue over budget.

The refusal is explicit and logged WITH the numbers (spent vs budget), so a run
that would over-spend stops honestly instead of grinding.
"""
from rag.budget import Budget
from rag.agent import run_agent


def test_budget_tracks_and_flags_over():
    b = Budget(max_calls=2, cost_per_call=0.001)
    b.charge(); b.charge()
    assert b.over() and abs(b.spent_usd() - 0.002) < 1e-9


def test_refusal_reports_numbers():
    b = Budget(max_calls=1)
    b.charge()
    line = b.refusal_line()
    assert "1" in line and "budget" in line.lower()


def test_agent_refuses_when_cost_budget_exhausted():
    planner = lambda goal, state: {"tool": "search", "args": {}}   # never drafts, never terminates
    st = run_agent("goal", [{"category": "MFO"}], planner, lambda g, d, f: "approved",
                   budget=99, cost_budget=Budget(max_calls=2))
    assert st.status == "refused"
    assert "budget" in (st.refuse_reason or "").lower()
    assert st.output is None
