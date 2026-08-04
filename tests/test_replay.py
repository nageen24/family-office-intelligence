"""Per-goal replay log — every goal run writes a JSONL trace of what happened, in
order: each tool call, each rejected path, errors, and the terminal verdict/refusal.
"""
import json
from rag.agent import AgentState
from rag.replay import replay_lines, write_replay


def _state():
    st = AgentState(goal="find healthcare MFOs")
    st.steps = [
        {"tool": "search", "args": {"focus": "healthcare"}, "result": {"matched": 3}},
        {"tool": "delete_all", "refused": "tool not in the agent's authority"},
        {"tool": "get_record", "error": "TypeError: x"},
    ]
    st.status = "refused"
    st.refuse_reason = "evidence too thin"
    return st


def test_replay_lines_are_ordered_and_typed():
    lines = replay_lines("find healthcare MFOs", _state())
    events = [l["event"] for l in lines]
    assert events == ["goal", "tool", "rejected", "error", "terminal"]
    assert lines[2]["tool"] == "delete_all"                 # the rejected path is captured
    assert lines[-1]["status"] == "refused"
    assert lines[-1]["refuse_reason"] == "evidence too thin"


def test_write_replay_produces_valid_jsonl(tmp_path):
    path = write_replay("find healthcare MFOs", _state(), out_dir=str(tmp_path))
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    assert rows[0]["event"] == "goal" and rows[-1]["event"] == "terminal"
    assert len(rows) == 5
