"""Budget guard — a per-run cost ledger with an explicit refusal.

Tracks the billable calls (and an optional $ estimate) a run has spent. When a run
reaches its budget, the agent refuses to continue and the refusal is logged WITH
the numbers — a bounded worker does not silently overrun its cost.
"""
from __future__ import annotations


class Budget:
    def __init__(self, max_calls: int, cost_per_call: float = 0.0):
        self.max_calls = max_calls
        self.cost_per_call = cost_per_call
        self.calls = 0

    def charge(self, n: int = 1) -> None:
        self.calls += n

    def over(self) -> bool:
        return self.calls >= self.max_calls

    def spent_usd(self) -> float:
        return round(self.calls * self.cost_per_call, 6)

    def refusal_line(self) -> str:
        return (f"[budget] REFUSE: spent {self.calls} calls "
                f"(${self.spent_usd():.4f}); budget is {self.max_calls} calls "
                f"— stopping instead of over-spending")

    def snapshot(self) -> dict:
        return {"calls": self.calls, "max_calls": self.max_calls,
                "spent_usd": self.spent_usd()}
