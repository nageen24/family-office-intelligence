"""S22 — structured, full-corpus retrieval over the real fields.

Stage 1 was semantic top-k. This adds exact multi-constraint filtering
(category, location, investing focus, commercial tier, trust) that ALWAYS runs on
the whole corpus and reports honest scope — eligible / matched / shown, plus any
constraint it could not honor. It is the deterministic tool the agent (S23) calls
and the basis for scope on every answer (S24 / fix#8).
"""
from __future__ import annotations

import csv
from typing import List, Optional

# supported constraints -> how each is applied to a record dict
_SUPPORTED = {"category", "location", "focus", "is_commercial", "trust", "min_trust"}
_TRUST_RANK = {"contradicted": 0, "stale": 1, "fresh": 2}


def load_records(csv_path: Optional[str] = None) -> List[dict]:
    from rag.ingest import default_csv
    path = csv_path or default_csv()
    try:
        return list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return []


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def _matches(rec: dict, c: dict) -> bool:
    if "category" in c and (rec.get("category") or "") != c["category"]:
        return False
    if "location" in c and c["location"].lower() not in (rec.get("hq_location") or "").lower():
        return False
    if "focus" in c and c["focus"].lower() not in (rec.get("investing_thesis") or "").lower():
        return False
    if "is_commercial" in c and _truthy(rec.get("is_commercial")) != bool(c["is_commercial"]):
        return False
    if "trust" in c and (rec.get("trust") or "") != c["trust"]:
        return False
    if "min_trust" in c:
        if _TRUST_RANK.get(rec.get("trust") or "", -1) < _TRUST_RANK.get(c["min_trust"], 99):
            return False
    return True


def search(records: List[dict], *, limit: Optional[int] = None, **constraints) -> dict:
    """Filter the FULL corpus by the supported constraints; report honest scope."""
    applied = {k: v for k, v in constraints.items() if k in _SUPPORTED and v is not None}
    unhonored = sorted(k for k, v in constraints.items()
                       if k not in _SUPPORTED and v is not None)
    hits = [r for r in records if _matches(r, applied)]
    shown = hits[:limit] if limit else hits
    return {
        "eligible": len(records),          # always the whole corpus
        "constraints": applied,
        "unhonored": unhonored,            # asked for but not held -> stated, never faked
        "matched": len(hits),
        "shown": len(shown),
        "hits": shown,
    }


def count(records: List[dict], **constraints) -> int:
    return search(records, **constraints)["matched"]


def get_record(records: List[dict], name: str) -> Optional[dict]:
    key = (name or "").lower().strip()
    for r in records:
        if key in (r.get("firm_name") or "").lower():
            return r
    return None
