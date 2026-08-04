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
        os.path.join(out_dir, "dataset_stage2.csv"), index=False)
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
        from rag.llm import chat as _chat
        chat = _chat

    state = load_state(state_path)
    todo = unattempted(candidates, state)[:batch_size]

    ledger = Ledger()
    rl = rate_limited(chat, min_interval=min_interval, ledger=ledger)
    from datetime import date
    today = date.today().isoformat()

    if todo:
        enrich_pool(todo, lambda f: enrich_one_firm(f, rl, fetch=fetch, ledger=ledger,
                                                    use_browser=use_browser,
                                                    add_news=add_news),
                    workers=workers, ledger=ledger)
        # Only merge firms that COMPLETED enrichment. A firm that threw (e.g. a
        # Groq rate-limit) is left out of state so it is retried next run, not
        # silently marked done with no data.
        failed = {id(f) for f in ledger.failures}
        done = [f for f in todo if id(f) not in failed]
        validate_all(done)
        # Apollo reach-recovery: fill LinkedIn/email (provider-returned, our own
        # validation) for function-proven firms still missing a personal route,
        # then re-validate so a recovered reach lets the record qualify.
        if _apollo_pass(done, apollo_email_budget, apollo_client):
            validate_all(done)
        for f in done:                       # stamp a freshly-proven source
            if f.proof_function_quote and not f.last_verified:
                f.last_verified, f.trust = today, "fresh"
        merge_pool(state, done)

    # S19 — cross-run staleness: re-check a few aging sources, adjust trust,
    # re-validate (a contradicted source loses its proof and the record drops).
    rechecked = _recheck_stale(state, fetch, today, limit=recheck_size, ledger=ledger)
    if todo or rechecked:
        save_state(state_path, state)

    _write_dataset(state, out_dir)
    summary = _summary(state, ledger, len(todo))
    summary["rechecked"] = rechecked
    return summary


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


def _recheck_stale(state: dict, fetch, today: str, limit: int, ledger=None) -> int:
    from pipeline.staleness import needs_recheck, apply_recheck
    targets = [f for f in state.values() if needs_recheck(f, today)][:limit]
    for f in targets:
        fresh = fetch(f.website) if f.website else None
        if ledger:
            ledger.bump("fetches")
        apply_recheck(f, fresh, today)
    if targets:
        validate_all(targets)                # contradicted -> proof gone -> drops
    return len(targets)


def main():
    import json
    batch = int(os.getenv("CLIMB_BATCH", "60"))
    use_browser = os.getenv("CLIMB_BROWSER", "").lower() in ("1", "true", "yes")
    # Groq free tier is ~30 req/min; 4 workers spaced 3s apart stays under it and
    # cut the 429 failures. The browser is heavier still, so go gentler there.
    workers = 2 if use_browser else 4
    interval = float(os.getenv("CLIMB_INTERVAL", "3.0"))
    apollo_emails = int(os.getenv("CLIMB_APOLLO_EMAILS", "20"))
    print(json.dumps(climb_once(batch_size=batch, use_browser=use_browser,
                                workers=workers, min_interval=interval,
                                apollo_email_budget=apollo_emails), indent=2))


if __name__ == "__main__":
    main()
