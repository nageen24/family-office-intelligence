"""S16/S17 — one climb increment for the scheduler.

Each run: discover prioritized candidates -> take the next batch NOT already in
durable state -> beyond-seed enrich (concurrent, rate-limited) -> validate ->
merge into state -> rewrite the accumulating dataset. Idempotent and restart-safe
(see pipeline.state). The GitHub Actions scheduler calls `python -m pipeline.climb`
and commits the changed state + dataset, so the run history + accumulated records
live in git.
"""
from __future__ import annotations

import os
from typing import Callable, List, Optional

import pandas as pd

from pipeline.schema import CandidateFirm
from pipeline.state import (STATE_PATH, load_state, save_state, unattempted,
                            merge_pool, firm_key)
from pipeline.phase2 import enrich_one_firm
from pipeline.enrichment.function_proof import fetch_site_text
from pipeline.validation.validate import validate_all
from pipeline.runner import Ledger, rate_limited, enrich_pool
from pipeline.ontology import counts_toward_500, Status, RouteType

FINAL = os.path.join("data", "final")
CANDIDATES_PATH = os.path.join("data", "state", "candidates.json")


def discover_candidates() -> List[CandidateFirm]:
    """Prioritized candidate stream.

    Prefer a COMMITTED candidate list (built where SEC is reachable) so the
    scheduler doesn't depend on the Actions runner being able to reach SEC. Falls
    back to a live ADV discovery when the committed file is absent.
    """
    if os.path.exists(CANDIDATES_PATH):
        return list(load_state(CANDIDATES_PATH).values())
    from pipeline.discovery.sec_adv import SECFormADV
    return SECFormADV().discover(limit=100000)


def _write_dataset(state: dict, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    firms = list(state.values())
    qualifying = [f for f in firms if f.record_status == "Qualified"]
    pd.DataFrame([f.to_flat_row() for f in qualifying]).to_csv(
        os.path.join(out_dir, "dataset.csv"), index=False)
    # full audit surface (every attempted firm, withheld values shown)
    pd.DataFrame([f.to_flat_row(audit=True) for f in firms]).to_csv(
        os.path.join(out_dir, "climb_audit.csv"), index=False)
    return len(qualifying)


def _summary(state: dict, ledger: Ledger, processed: int) -> dict:
    firms = list(state.values())
    q = [f for f in firms if f.record_status == "Qualified"]
    cats: dict = {}
    for f in q:
        cats[f.category.value] = cats.get(f.category.value, 0) + 1
    verified_personal = sum(
        1 for f in q if f.principal_email.status is Status.VERIFIED
        and f.principal_email.route is RouteType.PERSONAL)
    named = sum(1 for f in q if not f.principal_name.is_blank())
    snap = ledger.snapshot()
    return {
        "processed_this_run": processed,
        "attempted_total": len(state),
        "qualified_total": len(q),
        "by_category": cats,
        "named_principals": named,
        "verified_personal_emails": verified_personal,
        "ledger": snap,
    }


def climb_once(batch_size: int = 60, workers: int = 6, min_interval: float = 2.0,
               state_path: str = STATE_PATH, out_dir: str = FINAL,
               candidates: Optional[List[CandidateFirm]] = None,
               chat: Optional[Callable] = None,
               fetch: Callable[[str], str] = fetch_site_text,
               use_browser: bool = False, add_news: bool = True,
               recheck_size: int = 15, apollo_email_budget: int = 20,
               apollo_client=None) -> dict:
    if candidates is None:
        candidates = discover_candidates()
    if chat is None:
        from rag.llm import chat as _chat, reset_provider_stats
        reset_provider_stats()               # per-run provider health, read into summary
        # Bulk extraction runs on each provider's SMALL model and round-robins
        # across all configured free providers (Groq x2 / Cerebras / Gemini).
        # Rate limits are per provider AND per model, so this both
        # dodges any single model's daily cap (the 70b 100k-TPD leak) and ADDS
        # the providers' daily budgets together. Honesty is unaffected:
        # quote_present code-verifies every quote, so a weaker/other model can
        # only miss proofs, never fake them.
        chat = lambda system, user: _chat(system, user, small=True)

    state = load_state(state_path)
    # Interleave name-only firms (EDGAR/990/News/CIK) THROUGH the website-bearing
    # ones in the remaining pool, so every batch is a source mix instead of pure
    # ADV. Applied to the UNATTEMPTED stream (not the static file) so the ratio
    # holds regardless of what earlier runs already took. Name-only firms become
    # qualifiable once the browser layer (use_browser) finds their website.
    from pipeline.build_candidates import interleave_name_only
    todo = interleave_name_only(unattempted(candidates, state))[:batch_size]

    ledger = Ledger()
    rl = rate_limited(chat, min_interval=min_interval, ledger=ledger)
    from datetime import date
    today = date.today().isoformat()

    def process(firms):
        return _process_batch(firms, rl, fetch, ledger, use_browser, add_news,
                              apollo_email_budget, apollo_client, workers, today)

    # Proof-standard re-check: withhold any stored function-proof quote that fails
    # the tightened IS/operates-as gate (serving families / 'family office
    # services' / family-owned RIA no longer qualify). Runs every run so the whole
    # accumulated set stays at the current standard, not just newly-processed firms.
    withheld = _retighten_function_proofs(state)

    if todo:
        merge_pool(state, process(todo))

    # S19 — cross-run staleness: re-check aging sources, adjust trust, re-validate
    # (a contradicted source loses its proof and the record drops out of the set).
    rechecked, demoted, catches = _recheck_stale(state, fetch, today,
                                                 limit=recheck_size, ledger=ledger)

    # Self-replenishing quarantine loop: for every qualifying record the recheck
    # demoted, promote the next un-attempted candidate to hold the count.
    replenished = 0
    repl: List[CandidateFirm] = []
    if demoted:
        repl = unattempted(candidates, state)[:demoted]
        if repl:
            merge_pool(state, process(repl))
            replenished = len(repl)
            print(f"[replenish] {demoted} demoted -> promoted {replenished} "
                  f"candidate(s) to hold the count")

    # Escalation runs over the WHOLE state every run (idempotent), so a record a
    # later re-validation would silently re-decide stays parked as Review until
    # a human resolves its needs_human.json case.
    from pipeline.escalation import escalate_ambiguous
    parked = escalate_ambiguous(state.values())

    if todo or rechecked or replenished or parked or withheld:
        save_state(state_path, state)

    _write_dataset(state, out_dir)
    # self-report the shipped file so a reviewer's recount matches ours
    from pipeline.report import write_report
    try:
        write_report(dataset_path=os.path.join(out_dir, "dataset.csv"))
    except Exception as e:
        print(f"[report] skipped: {type(e).__name__}: {str(e)[:60]}")
    summary = _summary(state, ledger, len(todo))
    summary.update(rechecked=rechecked, demoted=demoted, replenished=replenished,
                   staleness_catches=catches, needs_human=parked,
                   proof_retightened=withheld)
    # which LLM providers actually served calls this run — a provider with all
    # errors is dead weight (bad key/model) and forfeits its share of the TPD.
    try:
        from rag.llm import provider_stats
        summary["provider_health"] = provider_stats()
    except Exception:
        pass
    # per-firm failure breakdown — the audit trail for the proof leak: why each
    # attempted firm produced no function proof (this run, and state-wide).
    attempted = todo + repl
    summary["fail_reasons_this_run"] = _reason_counts(attempted)
    summary["fail_reasons_state"] = _reason_counts(
        [f for f in state.values() if not f.proof_function_quote])
    return summary


def _reason_counts(firms) -> dict:
    counts: dict = {}
    for f in firms:
        r = getattr(f, "fail_reason", None)
        if r:
            # group llm-errors by exception type but keep that type visible
            r = ":".join(r.split(":")[:2]) if r.startswith("llm-error") else r
            counts[r] = counts.get(r, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _process_batch(firms, rl, fetch, ledger, use_browser, add_news,
                   apollo_email_budget, apollo_client, workers, today):
    """Enrich -> validate -> Apollo-recover -> stamp one batch; return the firms
    that completed (a firm that threw is left out to retry next run)."""
    def _enrich(f):
        try:
            enrich_one_firm(f, rl, fetch=fetch, ledger=ledger,
                            use_browser=use_browser, add_news=add_news)
        except Exception as e:
            # stamp WHY before the pool's fault isolation swallows the exception,
            # so the run summary can show a per-firm failure breakdown
            if not (f.fail_reason or "").startswith("llm-error"):
                f.fail_reason = f"llm-error: {type(e).__name__}: {str(e)[:80]}"
            raise
    enrich_pool(firms, _enrich, workers=workers, ledger=ledger)
    failed = {id(f) for f in ledger.failures}
    done = [f for f in firms if id(f) not in failed]
    validate_all(done)
    # reach-recovery for function-proven firms with no personal route: first the
    # Serper.dev LinkedIn lookup (keyed, capped), then Apollo (paid). Both graceful.
    recovered = _serper_pass(done)
    recovered = _email_finder_pass(done) or recovered
    recovered = _apollo_pass(done, apollo_email_budget, apollo_client) or recovered
    if recovered:
        validate_all(done)
    for f in done:
        if f.proof_function_quote and not f.last_verified:
            f.last_verified, f.trust = today, "fresh"
    return done


def _serper_pass(firms, client=None) -> int:
    """Find LinkedIn via Serper.dev for function-proven firms that have a named
    principal but no personal route. Graceful no-op without a Serper key."""
    from pipeline.enrichment.serper import Serper, enrich_serper
    from pipeline.validation.validate import _has_personal_reach
    client = client or Serper()
    if hasattr(client, "enabled") and not client.enabled():
        return 0
    gap = [f for f in firms
           if (f.proof_function_quote or f.sec_family_office_exemption)
           and not _has_personal_reach(f) and not f.principal_name.is_blank()]
    for f in gap:
        enrich_serper(f, client)
    return len(gap)


def _email_finder_pass(firms, hunter=None, snov=None) -> int:
    """Personal-email recovery via Hunter.io/Snov.io free tiers for function-
    proven firms with a named principal but no email. Strongest records spend
    the tiny monthly quotas first; graceful no-op without keys. Every accepted
    email enters as `inferred` — validate_all's own MX+SMTP check (which runs
    after this pass) decides whether it becomes `verified`."""
    from pipeline.enrichment.email_finder import (HunterClient, SnovClient,
                                                  enrich_email_finders)
    from pipeline.enrichment.apollo import is_strong
    hunter = hunter or HunterClient()
    snov = snov or SnovClient()
    if not (hunter.enabled() or snov.enabled()):
        return 0
    gap = [f for f in firms
           if (f.proof_function_quote or f.sec_family_office_exemption)
           and not f.principal_name.is_blank() and f.principal_email.is_blank()]
    gap.sort(key=is_strong, reverse=True)
    return sum(1 for f in gap if enrich_email_finders(f, hunter, snov))


def _apollo_pass(firms, email_budget: int, client=None) -> int:
    """Reach-recovery via Apollo for function-proven firms with no personal route.

    LinkedIn is fetched for every gap firm (recovers the reach gate); the scarce
    free-tier email credits are spent only on the strongest records, strongest
    first. Graceful no-op when no APOLLO_API_KEY is configured."""
    from pipeline.enrichment.apollo import ApolloClient, enrich_apollo, is_strong
    from pipeline.validation.validate import _has_personal_reach
    client = client or ApolloClient()
    if not getattr(client, "key", client):      # stub clients are truthy; live needs a key
        return 0
    gap = [f for f in firms
           if (f.proof_function_quote or f.sec_family_office_exemption)
           and not _has_personal_reach(f)]
    gap.sort(key=is_strong, reverse=True)        # best records get the email credits
    used = 0
    for f in gap:
        reveal = is_strong(f) and used < email_budget
        if reveal:
            used += 1
        enrich_apollo(f, client, reveal_email=reveal)
    return len(gap)


def _retighten_function_proofs(state: dict) -> int:
    """Bring every stored function proof to the CURRENT FO-identity gate, both ways:

    - WITHHOLD a live proof quote that fails the gate (kept in
      quarantined_function_quote for audit; the record drops from Qualified).
    - RESTORE a previously-quarantined quote that passes the gate now (e.g. after
      the gate was refined to accept bare-predicate taglines) so a real family
      office returns to proven.

    Idempotent; re-derives category + record_status. Returns the number of
    records whose proof state changed this pass."""
    from pipeline.ontology import establishes_fo_function
    n = 0
    for f in state.values():
        live = f.proof_function_quote
        if live and not establishes_fo_function(live):
            f.quarantined_function_quote = live
            f.proof_function_quote = None
            f.proof_type_quote = None
            f.sec_family_office_exemption = False
            f.fail_reason = "not-fo-identity-statement"
            n += 1
        elif not live and f.quarantined_function_quote \
                and establishes_fo_function(f.quarantined_function_quote):
            f.proof_function_quote = f.quarantined_function_quote
            f.proof_function_source = f.proof_function_source or f.website
            f.quarantined_function_quote = None
            f.fail_reason = None
            n += 1
    if n:
        validate_all(list(state.values()))       # re-derive category + record_status
    return n


def _recheck_stale(state: dict, fetch, today: str, limit: int, ledger=None):
    """Return (rechecked, demoted) — demoted = records that were Qualified and,
    after the re-check, no longer are (their source contradicted the stored proof)."""
    from pipeline.staleness import needs_recheck, apply_recheck
    # The re-check age must fit inside the 5-day operating window — the old
    # 14-day default meant staleness could NEVER fire during the mandate. At 2
    # days every proven record is re-confirmed (or caught changed) mid-window,
    # and the pass is fetch-only, so it costs no LLM tokens.
    max_age = int(os.getenv("CLIMB_RECHECK_DAYS", "2"))
    targets = [f for f in state.values()
               if needs_recheck(f, today, max_age_days=max_age)][:limit]
    was_qualified = {id(f) for f in targets if f.record_status == "Qualified"}
    for f in targets:
        fresh = fetch(f.website) if f.website else None
        if ledger:
            ledger.bump("fetches")
        apply_recheck(f, fresh, today)
    if targets:
        validate_all(targets)                # contradicted -> proof gone -> drops
    demoted = sum(1 for f in targets
                  if id(f) in was_qualified and f.record_status != "Qualified")
    # every non-fresh outcome is a catch: the firm, what changed, and the
    # evidence-based reason — this is the operating-window staleness proof
    catches = [{"firm": f.firm_name, "trust": f.trust,
                "reason": f.staleness_reason}
               for f in targets if f.trust in ("stale", "contradicted")]
    return len(targets), demoted, catches


def _run_settings(n: int, use_browser: bool) -> tuple[int, float, int]:
    """(batch, interval, workers) scaled to the number of configured LLM providers.

    Daily token budget (TPD) is PER PROVIDER, so total daily throughput scales
    ~linearly with provider count. Each free small-model tier is ~500k TPD; a firm
    costs ~3.4k tokens (~1.8 calls) => ~150 firms/day/provider, over 8 scheduled
    runs/day = ~18 firms/run/provider. Global call spacing must keep EACH provider
    under its ~6k TPM once calls are split n ways: (60/interval)*2k/n < 6k =>
    interval > 20/n. LLM calls are globally serialised, so workers only overlap
    fetch/browser I/O with the LLM wait; chromium is memory-heavy, so stay modest."""
    n = max(n, 1)
    batch = min(120, max(35, 18 * n))
    interval = min(10.0, max(4.0, 20.0 / n))
    workers = 3 if use_browser else 6
    return batch, interval, workers


def main():
    import json
    from rag.llm import provider_count
    n = provider_count()                         # configured free LLM providers
    use_browser = os.getenv("CLIMB_BROWSER", "").lower() in ("1", "true", "yes")
    d_batch, d_interval, d_workers = _run_settings(n, use_browser)

    # env overrides; an empty CLIMB_BATCH (as a scheduled run passes) falls back
    # to the provider-scaled default.
    _b = (os.getenv("CLIMB_BATCH") or "").strip()
    batch = int(_b) if _b else d_batch
    interval = float(os.getenv("CLIMB_INTERVAL") or d_interval)
    workers = int(os.getenv("CLIMB_WORKERS") or d_workers)
    apollo_emails = int(os.getenv("CLIMB_APOLLO_EMAILS", "20"))
    print(f"[climb] providers={n} batch={batch} interval={interval}s "
          f"workers={workers} browser={use_browser}")
    summary = climb_once(batch_size=batch, use_browser=use_browser,
                         workers=workers, min_interval=interval,
                         apollo_email_budget=apollo_emails)
    _append_run_history(summary)
    print(json.dumps(summary, indent=2))


RUN_HISTORY = os.path.join("data", "state", "run_history.jsonl")


def _append_run_history(summary: dict, path: str = RUN_HISTORY) -> None:
    """Append a one-line, timestamped record of this run to a COMMITTED file, so
    the operating window (run cadence, staleness catches, failures) is a durable
    repo artifact, not just an Actions-log entry that ages out."""
    import json
    from datetime import datetime, timezone
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "processed": summary.get("processed_this_run"),
        "attempted_total": summary.get("attempted_total"),
        "qualified_total": summary.get("qualified_total"),
        "rechecked": summary.get("rechecked"),
        "demoted": summary.get("demoted"),
        "staleness_catches": summary.get("staleness_catches"),
        "proof_retightened": summary.get("proof_retightened"),
        "needs_human": summary.get("needs_human"),
        "provider_health": summary.get("provider_health"),
        "fail_reasons_this_run": summary.get("fail_reasons_this_run"),
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


if __name__ == "__main__":
    main()
