"""Per-goal replay log.

Every goal run writes a JSONL trace — one line per event, in order: the goal, each
tool call (with args + result), each rejected path (a tool outside authority), any
error, and the terminal verdict (approved / refused / escalated / stopped) with its
reason. The raw unedited trace is the audit record for a goal, alongside the agent's
structured output.
"""
from __future__ import annotations

import json
import os
import re
import time


def replay_lines(goal: str, state) -> list[dict]:
    out = [{"seq": 0, "event": "goal", "goal": goal}]
    for i, s in enumerate(state.steps, 1):
        if s.get("refused"):
            out.append({"seq": i, "event": "rejected", "tool": s.get("tool"),
                        "reason": s["refused"]})
        elif s.get("error"):
            out.append({"seq": i, "event": "error", "tool": s.get("tool"),
                        "error": s["error"]})
        else:
            out.append({"seq": i, "event": "tool", "tool": s.get("tool"),
                        "args": s.get("args"), "result": s.get("result")})
    out.append({"seq": len(state.steps) + 1, "event": "terminal",
                "status": state.status, "release": getattr(state, "release", None),
                "refuse_reason": getattr(state, "refuse_reason", None)})
    return out


def write_replay(goal: str, state, out_dir: str = "data/goals") -> str:
    os.makedirs(out_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", (goal or "goal").lower()).strip("-")[:40]
    path = os.path.join(out_dir, f"{slug}-{int(time.time())}.jsonl")
    lines = replay_lines(goal, state)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    print(f"[replay] wrote {len(lines)} events -> {path}")
    return path
