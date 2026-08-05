# FAILURES.md — real failures, what the system did, and the fix trail

Raw evidence only. Every claim links to a run log, commit, or state file in this repo.

---

## 1. Groq token-per-day exhaustion (mass enrichment failure)

**Symptom.** Scheduled runs completed "green" while ~85% of each batch failed enrichment.
Run log (scheduled, 2026-08-05 11:23Z): <https://github.com/nageen24/family-office-intelligence/actions/runs/31001277981>
— summary in the log: `"processed_this_run": 60, "failed": 50, "llm_calls": 71, "qualified_total": 4`.
Same signature on 2026-08-04 08:31Z (this run also hit a push race and is the one red run in the Actions tab): <https://github.com/nageen24/family-office-intelligence/actions/runs/30892292596> — `"failed": 51`.

**What the system did.** Per-firm fault isolation (`pipeline/runner.py`) caught each
exception, left the failed firm OUT of durable state so it would be retried next run,
and completed the run. No corrupt records; the failure mode was silent throughput
loss, invisible because no per-firm reason was recorded.

**Root cause (found by instrumentation, not guessing).** Commit
[`93c9f8d`](https://github.com/nageen24/family-office-intelligence/commit/93c9f8d)
added a per-firm `fail_reason`; the first instrumented batch returned
`llm-error: 52, fetch-error: 6, no-proof-language-found: 2`. Direct probe of the
provider returned, on both keys:

```
429 {"error":{"message":"Rate limit reached for model `llama-3.3-70b-versatile` ...
on tokens per day (TPD): Limit 100000, Used 99674 ..."}}
```

Both Groq accounts had exhausted the 70b model's 100,000 tokens-per-day cap; retries
and key-failover cannot clear a daily cap.

**Fix.** Same commit [`93c9f8d`](https://github.com/nageen24/family-office-intelligence/commit/93c9f8d):
bulk extraction moved to `llama-3.1-8b-instant` (Groq limits are per-model, so it has
its own larger daily budget), the two keys are round-robined (per-key budgets add),
pacing went token-bound (2 workers, 10s call spacing). The verbatim-quote control
(`ontology.quote_present`) is unchanged — a weaker model can miss proofs, never fake them.

**Recovery run.** First full batch after the fix, committed in
[`d9eae9b`](https://github.com/nageen24/family-office-intelligence/commit/d9eae9b):
`"processed_this_run": 60, "failed": 0`, fail breakdown
`no-proof-language-found: 44, fetch-error: 8, quote-not-verbatim: 1`, qualified 5 → 7.
llm-error went 52 → 0.

---

## 2. Empty Serper key (silent no-op of the LinkedIn reach recovery)

**Symptom.** The Serper.dev LinkedIn-recovery pass shipped in commit
[`0d49803`](https://github.com/nageen24/family-office-intelligence/commit/0d49803)
(2026-08-04 15:17Z), but the `SERPER_API_KEY` repository secret was only created
2026-08-05 13:42:23Z (`gh secret list` timestamp). Every scheduled run in between —
seven runs, e.g. 2026-08-04 16:55Z <https://github.com/nageen24/family-office-intelligence/actions/runs/30931464106>
through 2026-08-05 11:23Z <https://github.com/nageen24/family-office-intelligence/actions/runs/31001277981> —
executed with an empty key.

**What the system did.** `Serper.enabled()` returned False and the pass no-op'd by
design (`pipeline/climb.py::_serper_pass`), so runs stayed green and no wrong data was
produced — but zero LinkedIn recoveries happened for 7 runs and nothing surfaced it.

**Fix.** Secret set 2026-08-05 13:42Z. The related cross-run gap — the committed daily
quota counter (`data/state/serper_quota.json`) was never persisted by the workflow, so
each runner started at zero — was fixed in
[`6be8870`](https://github.com/nageen24/family-office-intelligence/commit/6be8870)
(quota files now committed by every run).

**Recovery.** `data/state/serper_quota.json` now shows real spend
(`{"date": "2026-08-05", "count": 4}` — four live queries on the first keyed runs).

---

Both failures share the pattern the instrumentation now guards against: graceful
degradation without per-item accounting reads as success. `fail_reason` (per firm, in
`data/final/climb_audit.csv`) and `fail_reasons_this_run` / `staleness_catches` (per
run, in the Actions log) exist so the next silent leak is visible in one run, not five.
