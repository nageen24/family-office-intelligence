"""S24 — product language: 5 states + honest scope on every answer.

Every response is exactly one of these states, each rendered as a plain message a
first-time user understands, and always carrying its true scope:

  answered      - results found and released
  nothing_found - the query was valid but nothing in the corpus matched
  partial       - answered, but a requested constraint could not be honored
  declined      - the release authority refused/escalated (weak evidence) — an
                  honest abstention, not a guess
  error         - the system itself failed (say so; don't dress it as a decline)

Scope is stated for aggregate/list answers (which run on the FULL corpus) so the
reader always knows eligible / matched / shown and any unhonored constraint.
"""
from __future__ import annotations

STATES = {"answered", "nothing_found", "partial", "declined", "error"}


def _scope_line(scope: dict) -> str:
    parts = [f"Searched the full corpus of {scope['eligible']} records",
             f"{scope['matched']} matched"]
    if scope.get("shown") is not None and scope["shown"] != scope["matched"]:
        parts.append(f"showing {scope['shown']}")
    if scope.get("unhonored"):
        parts.append("could NOT honor: " + ", ".join(scope["unhonored"])
                     + " (that field isn't held, so it was not applied)")
    if scope.get("note"):
        parts.append(scope["note"])
    return "; ".join(parts) + "."


def respond(result: dict) -> dict:
    """Map a structured-search result OR an agent-state dict to a product state."""
    if result.get("error"):
        return {"state": "error", "scope": {}, "hits": [],
                "scope_line": f"Our answering service failed: {result['error']}. "
                              "This is on our side, not your question.",
                "message": "Something went wrong on our end — please retry shortly."}

    # --- agent-driven answer ---
    if "status" in result:
        s = result["status"]
        findings = result.get("findings", [])
        scope = {"eligible": result.get("eligible", len(findings)),
                 "matched": len(findings), "shown": len(findings)}
        if s == "done":
            return {"state": "answered", "scope": scope, "output": result.get("output"),
                    "scope_line": _scope_line(scope),
                    "message": "Answer released after independent review."}
        if s in ("refused", "escalated"):
            scope["note"] = ("escalated for human review" if s == "escalated"
                             else "the evidence did not support a confident answer")
            return {"state": "declined", "scope": scope, "output": None,
                    "scope_line": _scope_line(scope),
                    "message": "We can't answer this confidently from the data — "
                               "so we're not guessing."}
        # stopped (budget) -> partial
        scope["note"] = "the agent hit its step budget before finishing"
        return {"state": "partial", "scope": scope, "output": result.get("output"),
                "scope_line": _scope_line(scope), "message": "Partial result."}

    # --- structured / aggregate answer ---
    scope = {"eligible": result["eligible"], "matched": result["matched"],
             "shown": result.get("shown", result["matched"]),
             "unhonored": result.get("unhonored", [])}
    hits = result.get("hits", [])
    if result["matched"] == 0:
        return {"state": "nothing_found", "scope": scope, "hits": [],
                "scope_line": _scope_line(scope),
                "message": "No records in the corpus match that."}
    state = "partial" if scope["unhonored"] else "answered"
    return {"state": state, "scope": scope, "hits": hits,
            "scope_line": _scope_line(scope),
            "message": f"{result['matched']} matching records."}
