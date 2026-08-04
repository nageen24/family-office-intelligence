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
    count_result: Optional[int] = None   # last count(...) tool result, for scope


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
              budget: int = 8, state: Optional[AgentState] = None,
              cost_budget=None) -> AgentState:
    tools = _tools(records)
    st = state or AgentState(goal=goal)
    st.status = "running"

    while st.status == "running":
        if st.budget_used >= budget:
            st.status = "stopped"
            break
        # cost budget: refuse (with numbers, logged) before over-spending
        if cost_budget is not None and cost_budget.over():
            st.status = "refused"
            st.refuse_reason = cost_budget.refusal_line()
            print(st.refuse_reason)
            break

        action = planner(goal, st)
        if cost_budget is not None:
            cost_budget.charge()          # the planner turn was a billable LLM call

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
        # A count(...) result IS the deliverable for a counting goal: once it's in,
        # the agent has its answer, so it terminates here instead of looping until
        # the budget kills it and the run is mislabeled 'partial'. The count still
        # passes through the SAME independent release authority — the worker never
        # certifies itself.
        if tool == "count" and isinstance(result, dict) and "count" in result:
            n = st.count_result = result["count"]
            st.draft = {"answer": f"{n} matching record{'' if n == 1 else 's'}",
                        "count": n, "scope": "full corpus"}
            verdict = reviewer(goal, st.draft, st.findings)
            st.release = verdict if verdict in ("approved", "refused", "escalated") else "refused"
            if st.release == "approved":
                st.output, st.status = st.draft, "done"
            elif st.release == "escalated":
                st.status = "escalated"
            else:
                st.status = "refused"
            break
    return st


import re as _re

_TOOLS_DESC = (
    "search(category?, location?, focus?, is_commercial?, trust?, min_trust?, limit?) "
    "- filter the full corpus, returns hits + scope; "
    "count(...same filters...) - number matching; "
    "get_record(name) - one firm by name.")

_PLANNER_SYS = (
    "You are a research worker with a fixed goal and a FIXED set of read-only tools:\n"
    f"  {_TOOLS_DESC}\n"
    "Each turn return ONLY JSON: either {\"tool\": <name>, \"args\": {...}} to gather "
    "evidence, or {\"final\": {\"shortlist\": [{\"firm\":..,\"confidence\":\"high|"
    "medium|low\",\"why\":..}], \"scope\": \"...\"}} when you have enough evidence, "
    "or {\"refuse\": \"<why you cannot answer from the data>\"}. Use ONLY the tools "
    "listed. Base every claim on tool results; never invent firms or fields.")

_REVIEWER_SYS = (
    "You are an INDEPENDENT release authority — NOT the worker. Given the goal, the "
    "worker's draft, and the evidence it gathered, decide if the draft is fully "
    "supported by the evidence and honest about confidence. Return ONLY one word: "
    "approved (evidence supports every claim), refused (overclaims / thin evidence / "
    "guesses), or escalated (genuinely ambiguous, needs a human). Weak evidence must "
    "be refused, not approved.")


def _json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = _re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    m = _re.search(r"\{.*\}", raw, _re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def llm_planner(chat: Callable[[str, str], str]) -> Planner:
    def planner(goal: str, state: "AgentState") -> dict:
        view = json.dumps({"goal": goal, "steps_so_far": state.steps[-6:],
                           "findings_count": len(state.findings)})[:4000]
        act = _json(chat(_PLANNER_SYS, view))
        return act or {"refuse": "planner returned no valid action"}
    return planner


def llm_reviewer(chat: Callable[[str, str], str]) -> Reviewer:
    def reviewer(goal: str, draft: dict, findings: list) -> str:
        payload = json.dumps({"goal": goal, "draft": draft,
                              "evidence_sample": findings[:20]})[:6000]
        verdict = (chat(_REVIEWER_SYS, payload) or "").strip().lower()
        for v in ("approved", "refused", "escalated"):
            if v in verdict:
                return v
        return "refused"
    return reviewer


def answer_goal(goal: str, csv_path: Optional[str] = None, budget: int = 8) -> AgentState:
    """Run the agent live: LLM worker + independent LLM release authority. An
    escalated verdict opens a human-review case (needs_human.json) and stops."""
    from rag.llm import chat
    from rag.structured import load_records
    st = run_agent(goal, load_records(csv_path),
                   llm_planner(chat), llm_reviewer(chat), budget=budget)
    if st.status == "escalated":
        from rag.escalation import open_case
        open_case(f"agent escalated: {goal}",
                  {"goal": goal, "draft": st.draft, "findings": len(st.findings)},
                  options=["approve as-is", "revise", "reject"])
    try:
        from rag.replay import write_replay
        write_replay(goal, st)          # raw ordered JSONL trace of this goal run
    except Exception:
        pass
    return st


def save_agent(path: str, st: AgentState) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(st), f, indent=2)


def load_agent(path: str) -> AgentState:
    with open(path, encoding="utf-8") as f:
        return AgentState(**json.load(f))
