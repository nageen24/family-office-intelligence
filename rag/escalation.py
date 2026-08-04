"""Escalation queue — a real file the agent writes to when it may NOT decide.

When the bounded agent hits something outside its authority (ambiguous SFO/MFO,
conflicting sources, an unsafe release), it opens a case in needs_human.json and
stops. A human reviews, decides, and resolve_case() applies the decision and marks
the record 'human-authorized' — the worker never authorizes its own escalation.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

NEEDS_HUMAN = os.path.join("data", "state", "needs_human.json")
LOG = os.path.join("data", "state", "human_decisions.log")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, cases: list) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)


def _log(line: str, log: str) -> None:
    print(line)
    os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def open_case(reason: str, context: dict, options: list | None = None,
              path: str = NEEDS_HUMAN, log: str = LOG) -> str:
    cases = _load(path)
    cid = uuid.uuid4().hex[:8]
    cases.append({"id": cid, "opened_at": _now(), "reason": reason,
                  "context": context, "options": options or [],
                  "status": "pending", "decision": None})
    _save(path, cases)
    _log(f"[escalation] OPENED {cid}: {reason} -> stopped for human review", log)
    return cid


def pending_cases(path: str = NEEDS_HUMAN) -> list:
    return [c for c in _load(path) if c["status"] == "pending"]


def resolve_case(case_id: str, decision: str, path: str = NEEDS_HUMAN,
                 log: str = LOG) -> dict | None:
    cases = _load(path)
    for c in cases:
        if c["id"] == case_id and c["status"] == "pending":
            c.update(status="resolved", decision=decision, resolved_at=_now(),
                     authorization="human-authorized")
            _save(path, cases)
            _log(f"[escalation] RESOLVED {case_id} human-authorized: {decision}", log)
            return c
    return None
