"""S8 — re-run the Stage-1 enriched pool through the corrected Stage-2 engine.

Under the locked ontology (strict Proof B: FO-function proven ONLY by the firm's
own filing/site statement or a SEC family-office exemption), none of the Stage-1
records carry the required own-source function proof, so all are relabeled
Unresolved-Quarantine. This is the honest fix#3 requalification: the old file's
"qualified" rested on bases the corrected standard rejects (13F-name,
press-possessive, SEC-operating, Wikidata-class).

Output is an AUDIT surface (audit=True): every withheld value + reason is shown.
The Stage-1 dataset.csv is left in place but marked stale (see
data/final/STALE_NOTICE.md) until Phase 2 repopulates it with records that meet
the new standard.
"""
from __future__ import annotations

import collections
import os

import pandas as pd

from pipeline.io_utils import load_pool, FINAL
from pipeline.validation.validate import validate_all

OUT = os.path.join(FINAL, "stage1_requalification.csv")


def main() -> dict:
    pool = load_pool("enriched")
    validate_all(pool)

    os.makedirs(FINAL, exist_ok=True)
    pd.DataFrame([f.to_flat_row(audit=True) for f in pool]).to_csv(OUT, index=False)

    cats = collections.Counter(f.category.value for f in pool)
    qualifying = sum(1 for f in pool if f.record_status == "Qualified")
    summary = {
        "input_firms": len(pool),
        "qualifying_under_corrected_standard": qualifying,
        "category_distribution": dict(cats),
        "with_own_source_function_quote": sum(1 for f in pool if f.proof_function_quote),
        "audit_csv": OUT,
    }
    return summary


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))
