"""S16 — durable, idempotent climb state.

The scheduled climb accumulates results across many runs. State is a dict keyed by
a stable firm key -> the processed CandidateFirm, persisted as JSON in a COMMITTED
location (data/state/, not gitignored). Properties:

- idempotent: a firm already in state is skipped (unattempted), so reruns never
  redo work and never duplicate a record.
- restart-safe: state is saved after each batch, so a crash loses at most the
  in-flight batch, which is simply re-attempted next run.
- replayable: the git history of the state file is the run-by-run replay log.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Dict, List

from pipeline.schema import CandidateFirm
from pipeline.io_utils import _cell_from_dict  # reuse cell hydration
from pipeline.schema import FirmType
from pipeline.ontology import FirmCategory

STATE_PATH = os.path.join("data", "state", "climb_pool.json")

_CELLS = ["aum", "investing_thesis", "mandate", "background", "principal_name",
          "principal_title", "principal_linkedin", "principal_email",
          "principal_phone", "recent_signal"]


def firm_key(firm: CandidateFirm) -> str:
    """Stable identity key: CIK when present, else normalized name."""
    if firm.cik and str(firm.cik).strip():
        return f"cik:{str(firm.cik).strip()}"
    return "name:" + "".join(ch for ch in (firm.firm_name or "").lower() if ch.isalnum())


def unattempted(candidates: List[CandidateFirm], state: Dict) -> List[CandidateFirm]:
    """Candidates whose key is not already in state (order preserved)."""
    return [c for c in candidates if firm_key(c) not in state]


def merge_pool(state: Dict[str, CandidateFirm], pool: List[CandidateFirm]) -> Dict:
    """Add/replace each firm by key (idempotent)."""
    for firm in pool:
        state[firm_key(firm)] = firm
    return state


def _firm_from_dict(r: dict) -> CandidateFirm:
    firm = CandidateFirm(firm_name=r.get("firm_name"),
                         discovery_source=r.get("discovery_source"))
    for k, v in r.items():
        if k in _CELLS:
            setattr(firm, k, _cell_from_dict(v or {}))
        elif k == "firm_type":
            firm.firm_type = FirmType(v) if v else FirmType.UNCONFIRMED
        elif k == "category":
            firm.category = FirmCategory(v) if v else None
        else:
            setattr(firm, k, v)
    return firm


def save_state(path: str, state: Dict[str, CandidateFirm]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in state.values()], f, indent=1, default=str)


def load_state(path: str) -> Dict[str, CandidateFirm]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    state: Dict[str, CandidateFirm] = {}
    for r in raw:
        firm = _firm_from_dict(r)
        state[firm_key(firm)] = firm
    return state
