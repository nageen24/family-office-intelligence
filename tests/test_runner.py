"""S12 — concurrency, rate-limit handling, retries, cost tracking.

The enrichment run makes thousands of site fetches + LLM calls against free tiers,
so it needs: a rate limiter (stay under Groq's limit), retries (transient network
/ 429), a cost/throughput ledger, and per-firm fault isolation (one bad firm must
not kill the run).
"""
import time

from pipeline.runner import Ledger, rate_limited, with_retry, enrich_pool


def test_rate_limited_enforces_min_interval_and_counts_calls():
    led = Ledger()
    calls = []
    wrapped = rate_limited(lambda t: calls.append(t) or "ok", min_interval=0.05, ledger=led)
    t0 = time.perf_counter()
    for _ in range(3):
        wrapped("x")
    assert time.perf_counter() - t0 >= 0.09          # 3 calls, >=2 gaps of 0.05
    assert led.snapshot()["llm_calls"] == 3


def test_with_retry_succeeds_after_transient_failures():
    n = {"i": 0}
    def flaky():
        n["i"] += 1
        if n["i"] < 3:
            raise ConnectionError("boom")
        return "done"
    assert with_retry(flaky, attempts=3, base=0) == "done"
    assert n["i"] == 3


def test_with_retry_raises_after_exhausting_attempts():
    import pytest
    with pytest.raises(ValueError):
        with_retry(lambda: (_ for _ in ()).throw(ValueError("nope")), attempts=2, base=0)


def test_enrich_pool_processes_all_and_isolates_failures():
    pool = list(range(6))
    def enrich_one(x):
        if x == 3:
            raise RuntimeError("bad firm")
    _, led = enrich_pool(pool, enrich_one, workers=4)
    snap = led.snapshot()
    assert snap["processed"] == 6
    assert snap["failed"] == 1                       # only the one bad firm
    assert snap["elapsed_s"] >= 0
