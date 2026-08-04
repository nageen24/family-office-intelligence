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
               use_browser: bool = False, add_news: bool = True) -> dict:
    if candidates is None:
        candidates = discover_candidates()
    if chat is None:
        from rag.llm import chat as _chat
        chat = _chat

    state = load_state(state_path)
    todo = unattempted(candidates, state)[:batch_size]

    ledger = Ledger()
    rl = rate_limited(chat, min_interval=min_interval, ledger=ledger)
    if todo:
        enrich_pool(todo, lambda f: enrich_one_firm(f, rl, fetch=fetch, ledger=ledger,
                                                    use_browser=use_browser,
                                                    add_news=add_news),
                    workers=workers, ledger=ledger)
        validate_all(todo)
        merge_pool(state, todo)
        save_state(state_path, state)

    _write_dataset(state, out_dir)
    return _summary(state, ledger, len(todo))


def main():
    import json
    batch = int(os.getenv("CLIMB_BATCH", "60"))
    use_browser = os.getenv("CLIMB_BROWSER", "").lower() in ("1", "true", "yes")
    workers = 2 if use_browser else 6      # the browser is heavy — go gentler
    print(json.dumps(climb_once(batch_size=batch, use_browser=use_browser,
                                workers=workers), indent=2))


if __name__ == "__main__":
    main()
