"""Run the three evaluation goals and save, per goal, the four artifacts under
data/goals/<slug>/: exact goal, manual-retrieval output, agent structured output,
and the raw unedited run log.

Goal 1 is our own commercial-search framing; Goal 2 is verbatim (it must openly
abstain / lower confidence on thin evidence); Goal 3 is a placeholder for the
user to fill.
"""
from __future__ import annotations

import json
import os
import re

GOALS_DIR = os.path.join("data", "goals")

GOAL_1 = ("Build a shortlist of multi-family offices in the dataset that could be "
          "a commercial outreach target: for each, give the named decision-maker, "
          "their personal contact route, what the firm says it does, and any dated "
          "signal — and flag any where the evidence is too thin to contact.")

GOAL_2 = ("Identify the family offices in the dataset that are the best fit for a "
          "lower-middle-market healthcare services fund seeking limited partners, "
          "and tell me how confident you are in each")

GOAL_3 = "<<PLACEHOLDER — user to fill Goal 3 text here, then re-run this goal>>"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def _manual_retrieval(goal: str) -> dict:
    """The manual path a human would use: semantic retrieve + structured read."""
    from rag.retrieve import retrieve
    from rag.structured import load_records
    r = retrieve(goal, k=50)
    return {
        "gated": r.get("gated"),
        "hit_count": len(r.get("hits", [])),
        "hits": [{k: h.get(k) for k in ("firm_name", "firm_type", "category",
                                        "reachability_score", "record_status")}
                 for h in r.get("hits", [])],
        "corpus_records": len(load_records()),
    }


def run_goal(name: str, goal: str, run_agent: bool = True) -> None:
    d = os.path.join(GOALS_DIR, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "goal.txt"), "w", encoding="utf-8") as f:
        f.write(goal + "\n")

    if not run_agent:
        with open(os.path.join(d, "NOTE.txt"), "w", encoding="utf-8") as f:
            f.write("Goal text is a placeholder; fill goal.txt then re-run:\n"
                    "  python -m scripts.run_goals\n")
        print(f"[{name}] placeholder written (not run)")
        return

    with open(os.path.join(d, "manual_retrieval.json"), "w", encoding="utf-8") as f:
        json.dump(_manual_retrieval(goal), f, indent=2)

    from rag.agent import answer_goal, save_agent
    st = answer_goal(goal)
    save_agent(os.path.join(d, "agent_output.json"), st)

    # the raw unedited run log written by write_replay (data/goals/<goal-slug>.jsonl)
    from rag.replay import write_replay
    log_path = write_replay(goal, st, out_dir=d)
    os.replace(log_path, os.path.join(d, "run_log.jsonl"))
    print(f"[{name}] status={st.status} release={st.release} "
          f"findings={len(st.findings)} log=run_log.jsonl")


def main():
    run_goal("goal1-commercial-shortlist", GOAL_1, run_agent=True)
    run_goal("goal2-healthcare-lp-fit", GOAL_2, run_agent=True)
    run_goal("goal3-placeholder", GOAL_3, run_agent=False)


if __name__ == "__main__":
    main()
