"""Deterministic release gate.

Before a composed (LLM) answer reaches the user, PLAIN CODE recomputes the corpus
counts from the CSV and blocks the answer if the LLM's numbers contradict them:

- a count attached to the base entity (family offices / records / firms) that
  EXCEEDS the true total is impossible -> block;
- a corpus-total claim ("N verified family offices", "dataset has N", "N in
  total") that does not equal the true total -> block.

Legitimate subset claims ("2 MFOs match") are left alone. This is a mechanical
control, not a prompt promise — the LLM cannot talk its way past it.
"""
from __future__ import annotations

import re
from collections import Counter

_ENTITY = r"(?:verified\s+)?(?:family offices?|records?|firms?)"
# a number stated as a corpus TOTAL
_TOTAL_CTX = [
    re.compile(rf"(\d[\d,]*)\s+{_ENTITY}\b", re.I),                       # "N ... family offices"
    re.compile(rf"(?:total|in total|altogether|holds?|contains?|has)\D{{0,20}}(\d[\d,]*)", re.I),
]


def recompute_truth(records: list) -> dict:
    return {"total": len(records),
            "by_category": dict(Counter(r.get("category") for r in records))}


def _nums(text: str, pat: re.Pattern) -> list[int]:
    out = []
    for m in pat.finditer(text or ""):
        try:
            out.append(int(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def release_gate(answer_text: str, truth: dict) -> dict:
    """Return {"ok", "reason"}; ok=False means block the answer."""
    total = truth["total"]

    # impossible: more of the base entity than exist
    for n in _nums(answer_text, _TOTAL_CTX[0]):
        if n > total:
            reason = f"answer claims {n} records but only {total} exist — blocked"
            print(f"[release-gate] BLOCK: {reason}")
            return {"ok": False, "reason": reason}

    # a corpus-total claim that doesn't match the recomputed total
    for pat in _TOTAL_CTX:
        for n in _nums(answer_text, pat):
            # only treat it as a TOTAL claim when the wording is a whole-corpus one
            if n != total and n >= total:            # >= total rules out subset counts
                reason = f"answer states total {n} but the corpus holds {total} — blocked"
                print(f"[release-gate] BLOCK: {reason}")
                return {"ok": False, "reason": reason}
    # explicit total wording (e.g. "8 verified family offices" as the tagline)
    tagline = re.search(rf"(\d[\d,]*)\s+verified\s+family offices?", answer_text or "", re.I)
    if tagline:
        n = int(tagline.group(1).replace(",", ""))
        if n != total:
            reason = f"answer's corpus tagline says {n}, recomputed {total} — blocked"
            print(f"[release-gate] BLOCK: {reason}")
            return {"ok": False, "reason": reason}
    return {"ok": True, "reason": None}
