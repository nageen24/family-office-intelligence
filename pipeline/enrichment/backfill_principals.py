"""Backfill principal decision-makers from 13F signature blocks.

The first enrichment pass read <name> from the wrong part of the 13F XML (the
cover page's otherManager list, e.g. AQR/FMR), so the human signer's name was
dropped for most firms. sec_13f.py now scopes to <signatureBlock>; this re-runs
the corrected extractor over the already-validated pool and re-writes the
delivered dataset via the same documented value ranking.

Discipline (per the assessment): only BLANK cells are filled, only from the
official SEC filing, stamped FACT / HIGH with the filing URL as source. No value
is invented or guessed — a firm with no 13F signer stays honestly blank.

    py -m pipeline.enrichment.backfill_principals
"""
from __future__ import annotations

from pipeline.io_utils import load_pool, save_pool, write_dataset
from pipeline.enrichment.sec_13f import enrich_from_13f
from pipeline.schema import Cell


def _count(pool, attr):
    return sum(0 if getattr(f, attr).is_blank() else 1 for f in pool)


def run():
    pool = load_pool("validated")
    before = {a: _count(pool, a) for a in
              ("principal_name", "principal_title", "principal_phone", "aum")}
    for f in pool:
        if f.cik:
            # Force AUM recompute: the stored value was parsed with the old
            # thousands/dollars heuristic that inflated dollar-reporting filers
            # 1000x (CVA $949B, etc.). Clearing it lets the corrected sec_13f
            # formula refill it; name/title/phone still only fill if blank.
            f.aum = Cell()
            enrich_from_13f(f)
    after = {a: _count(pool, a) for a in before}
    for a in before:
        print(f"[backfill] {a}: {before[a]} -> {after[a]}")
    save_pool(pool, "validated")
    print("[backfill]", write_dataset(pool))


if __name__ == "__main__":
    run()
