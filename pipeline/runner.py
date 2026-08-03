"""S12 — concurrency, rate-limiting, retries, and a cost/throughput ledger.

The Phase-2 run fetches thousands of firm sites and calls the LLM per firm on free
tiers. This module gives:
  - Ledger:        thread-safe counters + elapsed, for cost/throughput reporting.
  - rate_limited:  serialise LLM calls to stay under the provider's rate limit.
  - with_retry:    exponential backoff for transient network / 429 failures.
  - enrich_pool:   run a per-firm function across a thread pool with per-firm fault
                   isolation — one bad firm never kills the run.

Cost is $0 (free tiers); the ledger tracks call volume + elapsed so 'cost to
refresh 1 vs all 500' can be computed from real throughput, not a guess.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, Tuple


class Ledger:
    """Thread-safe run counters."""

    def __init__(self):
        self._lock = threading.Lock()
        self._c = {"processed": 0, "failed": 0, "llm_calls": 0,
                   "fetches": 0, "qualified": 0}
        self._t0 = time.perf_counter()

    def bump(self, key: str, n: int = 1) -> None:
        with self._lock:
            self._c[key] = self._c.get(key, 0) + n

    def snapshot(self) -> dict:
        with self._lock:
            snap = dict(self._c)
        snap["elapsed_s"] = round(time.perf_counter() - self._t0, 2)
        return snap


def with_retry(fn: Callable, attempts: int = 3, base: float = 0.5,
               exceptions: tuple = (Exception,)):
    """Call fn, retrying on `exceptions` with exponential backoff."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except exceptions as e:  # noqa: PERF203
            last = e
            if i < attempts - 1 and base:
                time.sleep(base * (2 ** i))
    raise last


def rate_limited(llm: Callable, min_interval: float,
                 ledger: "Ledger | None" = None,
                 attempts: int = 3) -> Callable:
    """Wrap a callable so calls are spaced >= min_interval apart (thread-safe) and
    retried on transient failure; counts each call in the ledger. Works for any
    signature (the LLM client takes system+user)."""
    lock = threading.Lock()
    last = [0.0]

    def wrapped(*args, **kwargs):
        with lock:
            gap = min_interval - (time.perf_counter() - last[0])
            if gap > 0:
                time.sleep(gap)
            last[0] = time.perf_counter()
        if ledger:
            ledger.bump("llm_calls")
        return with_retry(lambda: llm(*args, **kwargs), attempts=attempts, base=0.5)

    return wrapped


def enrich_pool(pool: Iterable, enrich_one: Callable, workers: int = 8,
                ledger: "Ledger | None" = None) -> Tuple[List, Ledger]:
    """Run enrich_one(item) across a thread pool with per-item fault isolation."""
    items = list(pool)
    led = ledger or Ledger()

    def work(item):
        try:
            enrich_one(item)
        except Exception:
            led.bump("failed")
        finally:
            led.bump("processed")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, items))
    return items, led
