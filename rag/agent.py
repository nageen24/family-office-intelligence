"""S23 — the real bounded agent.

A goal-driven worker with:
- BOUNDED TOOL AUTHORITY: it may only call tools in a fixed registry (search /
  count / get_record — deterministic, read-only over the corpus). Any other tool
  is refused, not executed.
- DURABLE STATE: AgentState is JSON-serialisable and can be saved/loaded to resume
  a run safely from where it stopped.
- EXPLICIT TERMINALS: done / refused / escalated / stopped (budget).
- INDEPENDENT RELEASE AUTHORITY: the worker proposes a draft, but a SEPARATE
  reviewer (never the worker) decides approve / refuse / escalate. The worker
  cannot certify its own output — any 'release' the worker writes is ignored.

The worker (planner) and the authority (reviewer) are injected callables so the
control flow is testable offline and LLM-backed in production.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Callable, List, Optional

from rag.structured import search, count, get_record

# Planner: (goal, state) -> {"tool","args"} | {"final": draft} | {"refuse": reason}
Planner = Callable[[str, "AgentState"], dict]
# Reviewer (release authority): (goal, draft, findings) -> "approved"|"refused"|"escalated"
Reviewer = Callable[[str, dict, list], str]


@dataclass
class AgentState:
    goal: str
    steps: List[dict] = field(default_factory=list)
    findings: List[dict] = field(default_factory=list)
    status: str = "running"          # running / done / refused / escalated / stopped
    draft: Optional[dict] = None
    release: Optional[str] = None    # set ONLY by the reviewer authority
    output: Optional[dict] = None    # set ONLY on approved release
    refuse_reason: Optional[str] = None
    budget_used: int = 0


def _tools(records: List[dict]) -> dict:
    """The agent's fixed, read-only authority. Nothing here mutates anything."""
    return {
        "search": lambda **kw: search(records, **kw),
        "count": lambda **kw: {"count": count(records, **kw)},
        "get_record": lambda name=None, **_: get_record(records, name or ""),
    }


def _summarize(result) -> dict:
    if isinstance(result, dict) and "hits" in result:
        return {"matched": result["matched"], "eligible": result["eligible"],
                "unhonored": result["unhonored"]}
    return {"result": result}


def run_agent(goal: str, records: List[dict], planner: Planner, reviewer: Reviewer,
              budget: int = 8, state: Optional[AgentState] = None) -> AgentState:
    tools = _tools(records)
    st = state or AgentState(goal=goal)
    st.status = "running"

    while st.status == "running":
        if st.budget_used >= budget:
            st.status = "stopped"
            break

        action = planner(goal, st)

        # worker proposes a final answer -> hand to the SEPARATE release authority
        if "final" in action:
            st.draft = {k: v for k, v in action["final"].items() if k != "release"}
            verdict = reviewer(goal, st.draft, st.findings)   # worker never decides this
            st.release = verdict if verdict in ("approved", "refused", "escalated") else "refused"
            if st.release == "approved":
                st.output, st.status = st.draft, "done"
            elif st.release == "escalated":
                st.status = "escalated"
            else:
                st.status = "refused"
            break

        # worker chooses to abstain
        if "refuse" in action:
            st.status, st.refuse_reason = "refused", action["refuse"]
            break

        tool = action.get("tool")
        st.budget_used += 1
        if tool not in tools:                       # bounded authority enforced in code
            st.steps.append({"tool": tool, "refused": "tool not in the agent's authority"})
            continue
        try:
            result = tools[tool](**action.get("args", {}))
        except Exception as e:
            st.steps.append({"tool": tool, "error": f"{type(e).__name__}: {e}"})
            continue
        st.steps.append({"tool": tool, "args": action.get("args", {}),
                         "result": _summarize(result)})
        if isinstance(result, dict) and result.get("hits"):
            st.findings.extend(result["hits"])
    return st


def save_agent(path: str, st: AgentState) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(st), f, indent=2)


def load_agent(path: str) -> AgentState:
    with open(path, encoding="utf-8") as f:
        return AgentState(**json.load(f))
