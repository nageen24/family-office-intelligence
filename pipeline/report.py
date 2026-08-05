"""Dataset self-reporting — counts computed FROM the shipped file.

The dataset must state its own qualifying-email count and per-source-class record
mix, computed from data/final/dataset.csv itself (not from in-memory state), so a
reviewer who re-counts the file gets the SAME numbers we publish. Every figure
here is reproducible with `python -m pipeline.report` against the committed CSV.

Emails are reported by honest status (S2 vocab): `verified` = our own SMTP
mailbox check confirmed it; `inferred` = provider/MX-only, not mailbox-confirmed.
Only verified-personal counts toward the 200-email gate; a shortfall is shown as
a shortfall, never rounded up.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Optional

import pandas as pd

DATASET = os.path.join("data", "final", "dataset.csv")
REPORT_MD = os.path.join("docs", "DATASET_REPORT.md")
EMAIL_GATE = 200


def _split_sources(value: str) -> list[str]:
    """A record found by >1 source stores 'A + B'; count each class it came from."""
    return [s.strip() for s in str(value or "").split(" + ") if s.strip()]


def compute(dataset_path: str = DATASET) -> dict:
    """Read the shipped dataset and return the self-report figures."""
    if not os.path.exists(dataset_path):
        return {"records": 0, "note": f"{dataset_path} not found"}
    df = pd.read_csv(dataset_path)
    n = len(df)

    def col(name):
        return df[name] if name in df.columns else pd.Series([None] * n)

    est = col("principal_email__status").fillna("")
    ert = col("principal_email__route").fillna("")
    has_email = col("principal_email").notna()

    verified_personal = int(((est == "verified") & (ert == "personal")).sum())
    inferred_personal = int(((est == "inferred") & (ert == "personal")).sum())
    any_email = int(has_email.sum())

    # source mix: per-class (a multi-source record counts under each class) and
    # the raw combined label (records counted once, under exactly what they store)
    per_class: Counter = Counter()
    for v in col("discovery_source"):
        for s in _split_sources(v):
            per_class[s] += 1
    combined = Counter(str(v) for v in col("discovery_source").fillna("(none)"))

    return {
        "records": n,
        "emails": {
            "verified_personal": verified_personal,
            "inferred_personal": inferred_personal,
            "any_email_present": any_email,
            "gate": EMAIL_GATE,
            "gate_shortfall": max(EMAIL_GATE - verified_personal, 0),
        },
        "source_mix_by_class": dict(per_class.most_common()),
        "source_mix_combined": dict(combined.most_common()),
    }


def render_markdown(stats: dict, dataset_path: str = DATASET) -> str:
    if stats.get("records", 0) == 0 and "note" in stats:
        return f"# Dataset self-report\n\n{stats['note']}\n"
    e = stats["emails"]
    lines = [
        "# Dataset self-report",
        "",
        f"Computed from `{dataset_path}` by `python -m pipeline.report`. "
        "Re-run it against the committed file and the numbers match — these are "
        "not hand-maintained.",
        "",
        f"**Qualifying records:** {stats['records']}",
        "",
        "## Principal emails (by honest status)",
        "",
        "| Measure | Count |",
        "| --- | ---: |",
        f"| Verified personal (our SMTP mailbox check passed) | {e['verified_personal']} |",
        f"| Inferred personal (provider/MX-only, not mailbox-confirmed) | {e['inferred_personal']} |",
        f"| Any principal email present | {e['any_email_present']} |",
        f"| 200-verified-email gate | {e['gate']} |",
        f"| Shortfall to gate | {e['gate_shortfall']} |",
        "",
    ]
    if e["gate_shortfall"] > 0:
        lines += [
            f"> Honest shortfall: {e['verified_personal']} of {e['gate']} "
            f"verified-personal emails. The gap is documented, not filled with "
            f"pattern-built or unverified addresses.",
            "",
        ]
    lines += [
        "## Source mix — records per discovery-source class",
        "",
        "A record found by more than one source is counted under each class it "
        "came from, so these can sum to more than the record count.",
        "",
        "| Discovery source class | Records |",
        "| --- | ---: |",
    ]
    for src, c in stats["source_mix_by_class"].items():
        lines.append(f"| {src} | {c} |")
    lines += ["", "### Exact stored labels (each record counted once)", "",
              "| discovery_source (as stored) | Records |", "| --- | ---: |"]
    for src, c in stats["source_mix_combined"].items():
        lines.append(f"| {src} | {c} |")
    lines.append("")
    return "\n".join(lines)


def write_report(dataset_path: str = DATASET, out_path: str = REPORT_MD) -> dict:
    stats = compute(dataset_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(stats, dataset_path))
    return stats


def main():
    import json
    stats = write_report()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
