"""S23 — the real bounded agent (Correction #9).

A goal-driven worker that may ONLY call a fixed set of deterministic tools
(bounded authority), keeps durable state (safe resume), and whose output is
released ONLY by a SEPARATE authority — the worker cannot certify itself. Explicit
terminals: done / refused / escalated / stopped(budget). The win on weak evidence
is honest abstention (refused), not a confident guess.
"""
from rag.agent import run_agent, AgentState, save_agent, load_agent

CORPUS = [
    {"firm_name": "Alpha MFO", "category": "MFO", "hq_location": "Dallas, TX",
     "investing_thesis": "lower-middle-market healthcare buyouts", "is_commercial": "True"},
    {"firm_name": "Beta FO", "category": "MFO", "hq_location": "Miami, FL",
     "investing_thesis": "real estate", "is_commercial": "True"},
]

DRAFT = {"shortlist": [{"firm": "Alpha MFO", "confidence": "high"}]}


def _planner(actions):
    it = iter(actions)
    return lambda goal, state: next(it)


def _approve(goal, draft, findings):
    return "approved"


def test_agent_runs_bounded_tools_then_releases_on_authority_approval():
    planner = _planner([
        {"tool": "search", "args": {"category": "MFO", "focus": "healthcare"}},
        {"final": DRAFT},
    ])
    st = run_agent("find healthcare MFOs", CORPUS, planner, _approve)
    assert st.status == "done"
    assert st.release == "approved"
    assert st.output == DRAFT
    assert st.steps[0]["tool"] == "search"


def test_agent_abstains_when_authority_refuses():
    planner = _planner([{"final": DRAFT}])
    st = run_agent("goal", CORPUS, planner, lambda g, d, f: "refused")
    assert st.status == "refused"
    assert st.output is None            # nothing released on weak evidence


def test_agent_escalates_when_authority_escalates():
    planner = _planner([{"final": DRAFT}])
    st = run_agent("goal", CORPUS, planner, lambda g, d, f: "escalated")
    assert st.status == "escalated"
    assert st.output is None


def test_worker_cannot_self_certify():
    # the worker's draft even claims it's approved — ignored; only the authority decides
    planner = _planner([{"final": {**DRAFT, "release": "approved"}}])
    st = run_agent("goal", CORPUS, planner, lambda g, d, f: "refused")
    assert st.release == "refused"
    assert st.output is None


def test_agent_refuses_a_tool_outside_its_authority():
    planner = _planner([
        {"tool": "delete_everything", "args": {}},
        {"final": DRAFT},
    ])
    st = run_agent("goal", CORPUS, planner, _approve)
    assert st.steps[0].get("refused")           # tool not executed
    assert "authority" in st.steps[0]["refused"]


def test_agent_stops_on_budget_exhaustion():
    planner = _planner([{"tool": "search", "args": {}}] * 10)   # never drafts
    st = run_agent("goal", CORPUS, planner, _approve, budget=3)
    assert st.status == "stopped"
    assert st.budget_used == 3


def test_count_result_is_captured_for_scope():
    # a count goal returns a number, not hits; the state must keep that number so
    # scope reports it instead of collapsing to "0 matched".
    planner = _planner([
        {"tool": "count", "args": {"category": "MFO"}},
        {"final": DRAFT},
    ])
    st = run_agent("how many MFOs", CORPUS, planner, _approve)
    assert st.status == "done"
    assert st.count_result == 2          # both CORPUS firms are MFO
    assert st.findings == []             # count carries no record hits


def test_count_goal_completes_instead_of_looping_to_budget():
    # regression: once the count is in, the agent must STOP and return 'done' —
    # not keep calling the planner until the budget kills it (which mislabels the
    # run 'stopped' -> 'partial'). This planner would loop forever if not stopped.
    planner = _planner([{"tool": "count", "args": {}}]
                       + [{"tool": "search", "args": {}}] * 20)
    st = run_agent("how many records are in the dataset", CORPUS, planner,
                   _approve, budget=8)
    assert st.status == "done"           # completed, not 'stopped'
    assert st.release == "approved"
    assert st.count_result == 2
    assert st.budget_used == 1           # stopped after the single count step
    assert st.output["count"] == 2


def test_count_goal_still_answers_to_the_independent_authority():
    # the count is not auto-trusted: it passes the SAME release authority. A
    # refusing authority yields 'refused', not a silent 'done'.
    planner = _planner([{"tool": "count", "args": {}}])
    st = run_agent("how many records", CORPUS, planner, lambda g, d, f: "refused")
    assert st.status == "refused"
    assert st.output is None


def test_durable_state_resumes(tmp_path):
    planner = _planner([{"tool": "search", "args": {"category": "MFO"}}, {"final": DRAFT}])
    st = run_agent("goal", CORPUS, planner, _approve, budget=1)   # stops after 1 step
    assert st.status == "stopped"
    path = str(tmp_path / "agent.json")
    save_agent(path, st)
    resumed = load_agent(path)
    assert resumed.goal == "goal"
    assert len(resumed.steps) == 1
    # resume with fresh budget -> reaches the draft and releases
    planner2 = _planner([{"final": DRAFT}])
    st2 = run_agent("goal", CORPUS, planner2, _approve, budget=5, state=resumed)
    assert st2.status == "done"
