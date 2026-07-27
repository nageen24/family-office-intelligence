"""Load/save the candidate pool between pipeline stages.

We persist the pool as JSON in data/interim so each stage (discovery ->
enrichment -> validation) can run independently and be inspected. The final
deliverables are written to data/final as CSV/XLSX.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import List

import pandas as pd

from pipeline.schema import CandidateFirm, Cell, FirmType, Confidence, Epistemic

INTERIM = os.path.join("data", "interim")
FINAL = os.path.join("data", "final")


def _cell_from_dict(d: dict) -> Cell:
    if not d:
        return Cell()
    return Cell(
        value=d.get("value"),
        source=d.get("source"),
        method=d.get("method"),
        confidence=Confidence(d["confidence"]) if d.get("confidence") else None,
        epistemic=Epistemic(d["epistemic"]) if d.get("epistemic") else None,
        asof_date=d.get("asof_date"),
    )


def save_pool(pool: List[CandidateFirm], name: str) -> str:
    os.makedirs(INTERIM, exist_ok=True)
    path = os.path.join(INTERIM, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in pool], f, indent=2, default=str)
    return path


def load_pool(name: str) -> List[CandidateFirm]:
    path = os.path.join(INTERIM, f"{name}.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    pool: List[CandidateFirm] = []
    cell_names = [
        "aum", "investing_thesis", "mandate", "background",
        "principal_name", "principal_title", "principal_linkedin",
        "principal_email", "principal_phone", "recent_signal",
    ]
    for r in raw:
        kwargs = {k: v for k, v in r.items() if k not in cell_names}
        kwargs["firm_type"] = FirmType(r.get("firm_type", "Unconfirmed"))
        firm = CandidateFirm(**{
            "firm_name": kwargs.get("firm_name"),
            "discovery_source": kwargs.get("discovery_source"),
        })
        # assign remaining scalar attributes
        for k, v in kwargs.items():
            setattr(firm, k, FirmType(v) if k == "firm_type" else v)
        for cn in cell_names:
            setattr(firm, cn, _cell_from_dict(r.get(cn) or {}))
        pool.append(firm)
    return pool


def write_dataset(pool: List[CandidateFirm]) -> dict:
    """Split pool into qualified dataset + rejection log and write files."""
    os.makedirs(FINAL, exist_ok=True)
    qualified = [c for c in pool if c.record_status == "Qualified"]
    rejected = [c for c in pool if c.record_status == "Rejected"]

    df_q = pd.DataFrame([c.to_flat_row() for c in qualified])
    df_r = pd.DataFrame([c.to_flat_row() for c in rejected])

    ds_csv = os.path.join(FINAL, "dataset.csv")
    ds_xlsx = os.path.join(FINAL, "dataset.xlsx")
    rej_csv = os.path.join(FINAL, "rejection_log.csv")

    df_q.to_csv(ds_csv, index=False)
    if not df_q.empty:
        df_q.to_excel(ds_xlsx, index=False)
    df_r.to_csv(rej_csv, index=False)

    return {
        "qualified": len(qualified),
        "rejected": len(rejected),
        "dataset_csv": ds_csv,
        "rejection_log": rej_csv,
    }
