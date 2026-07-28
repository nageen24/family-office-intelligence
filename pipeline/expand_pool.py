"""Additive pool expansion — widen discovery WITHOUT losing the existing pool.

Keeps every firm already discovered/enriched/validated, runs discovery again
(the news queries are widened + Wikidata/990 non-SEC sources), keeps only the
NEW firms, enriches and validates just those, then merges and re-ranks. The
delivered 50 is re-selected from the combined pool by the same value score, so
new non-SEC firms compete on merit and nothing already collected is discarded.

    py -m pipeline.expand_pool
"""
from __future__ import annotations

from typing import List

import pipeline.discovery  # noqa: F401 (registers sources)
from pipeline.discovery.base import all_sources
from pipeline.enrichment.enrich import enrich_all
from pipeline.validation.validate import validate_all
from pipeline.io_utils import load_pool, save_pool, write_dataset
from pipeline.schema import CandidateFirm


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def run():
    existing = load_pool("validated")
    have = {_norm(f.firm_name) for f in existing}
    print(f"[expand] existing pool: {len(existing)}")

    # discover across ALL sources; keep only names we don't already have
    fresh: List[CandidateFirm] = []
    seen = set()
    for src in all_sources():
        try:
            found = src.discover(limit=60)
        except Exception as e:
            print(f"[expand] {src.name} error: {e}")
            continue
        new = [f for f in found
               if _norm(f.firm_name) not in have and _norm(f.firm_name) not in seen]
        for f in new:
            seen.add(_norm(f.firm_name))
        fresh.extend(new)
        print(f"[expand]   {src.name}: +{len(new)} new")
    print(f"[expand] new candidates: {len(fresh)}")

    if fresh:
        fresh = enrich_all(fresh)
        fresh = validate_all(fresh)
        q = sum(1 for f in fresh if f.record_status == "Qualified")
        print(f"[expand] new qualified: {q}/{len(fresh)}")

    combined = existing + fresh
    save_pool(combined, "validated")
    print("[expand]", write_dataset(combined))


if __name__ == "__main__":
    run()
