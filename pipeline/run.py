"""End-to-end pipeline orchestrator.

    py -m pipeline.run --stage all

Stages (can run individually so we can inspect between them):
    discover  -> data/interim/discovered.json
    enrich    -> data/interim/enriched.json
    validate  -> data/final/dataset.csv + rejection_log.csv
    all       -> run the three in order

The 50-record file is produced by THIS pipeline. Manual work is limited to
leads (see discovery/supplementary.py) and spot-checks — never hand-compiling
the delivered records.
"""
from __future__ import annotations

import argparse
from typing import List

# importing the package triggers @register on each source
import pipeline.discovery  # noqa: F401
from pipeline.discovery.base import all_sources
from pipeline.enrichment.enrich import enrich_all
from pipeline.validation.validate import validate_all
from pipeline.io_utils import save_pool, load_pool, write_dataset
from pipeline.schema import CandidateFirm


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def dedup(pool: List[CandidateFirm]) -> List[CandidateFirm]:
    seen = {}
    for firm in pool:
        key = _norm(firm.firm_name)
        if key not in seen:
            seen[key] = firm
        else:
            # keep the richer record (prefer one with a signal or website)
            existing = seen[key]
            if (firm.website and not existing.website) or \
               (not firm.recent_signal.is_blank() and existing.recent_signal.is_blank()):
                seen[key] = firm
    return list(seen.values())


def stage_discover(per_source: int = 40) -> List[CandidateFirm]:
    pool: List[CandidateFirm] = []
    for src in all_sources():
        print(f"[discover] {src.name} ...")
        try:
            found = src.discover(limit=per_source)
            print(f"[discover]   +{len(found)} from {src.name}")
            pool.extend(found)
        except Exception as e:
            print(f"[discover]   error {src.name}: {e}")
    pool = dedup(pool)
    print(f"[discover] total unique candidates: {len(pool)}")
    save_pool(pool, "discovered")
    return pool


def stage_enrich() -> List[CandidateFirm]:
    pool = load_pool("discovered")
    pool = enrich_all(pool)
    save_pool(pool, "enriched")
    return pool


def stage_validate() -> dict:
    pool = load_pool("enriched")
    pool = validate_all(pool)
    save_pool(pool, "validated")
    result = write_dataset(pool)
    print(f"[validate] {result}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["discover", "enrich", "validate", "all"],
                    default="all")
    ap.add_argument("--per-source", type=int, default=40)
    args = ap.parse_args()

    if args.stage in ("discover", "all"):
        stage_discover(args.per_source)
    if args.stage in ("enrich", "all"):
        stage_enrich()
    if args.stage in ("validate", "all"):
        stage_validate()


if __name__ == "__main__":
    main()
