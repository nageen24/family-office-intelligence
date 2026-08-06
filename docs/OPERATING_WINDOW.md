# Operating-window proof

Factual evidence that the pipeline runs unattended over time, degrades gracefully
on a dependency failure, and self-corrects stale records across runs. Every claim
below points to a real file / commit / log. Judgment and "why this matters"
sentences are intentionally left blank for the reviewer to complete.

## Where each run is recorded

Each run appends one timestamped line to `data/state/run_history.jsonl` (committed
by the workflow), and the full JSON summary is in that run's GitHub Actions log.

_Reviewer note:_ ______________________________________________________________

## Condition 1 — scheduled runs spanning ≥ 48 hours

- Scheduled `climb` runs (cron every 3h) commit `climb: scheduled run <UTC> [skip ci]`.
- First: `2026-08-04 03:35:48 +0000`. Latest: `2026-08-06 15:09:21 +0000`.
- **Span: 59.0 hours across 15 scheduled runs** (`git log --grep "climb: scheduled run"`).

_Reviewer note:_ ______________________________________________________________

## Condition 2 — dependency failure, handled (INDUCED)

Nothing broke naturally in-window, so a source-side failure was **induced** and
labelled as such. Evidence: `data/state/induced_failure_evidence.json`.

- Action: the SEC EDGAR full-text endpoint host was replaced with an invalid host.
- Result: the source logged the error per query and returned 0 candidates; the
  run **continued without crashing**.
- Mechanism: per-source `try/except` in `pipeline/build_candidates.py` and
  `DiscoverySource.get` — a flaky/blocked source is logged and skipped, never
  sinks the run.

_Reviewer note:_ ______________________________________________________________

## Condition 3 — cross-run staleness catch

A later run re-checked a record an earlier run had processed and changed its trust
on evidence, recording the reason.

- Latest catch (in `data/state/run_history.jsonl`): **ALPHA CAPITAL FAMILY OFFICE,
  LLC → trust `stale`** — "source went dark on re-check 2026-08-06; kept the proof
  captured earlier but it can no longer be re-confirmed." Proof retained (going
  dark does not contradict a past proof); `demoted = 0`.
- Contradiction path (proof withheld, record dropped) is exercised by
  `tests/test_climb.py::test_recheck_detects_a_demotion_for_replenishment`.
- Engine: `pipeline/staleness.py` (`needs_recheck` / `apply_recheck`); the
  re-check age is `CLIMB_RECHECK_DAYS` (default 2) so it fires inside the window.

_Reviewer note:_ ______________________________________________________________
