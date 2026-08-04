"""Prediction tracker — compare the user's 3 Day-2 predictions against actual.

The user fills `predicted` in predictions.json. This script fills the measurable
`actual` from the final artifacts (qualified record count + a per-record / all-500
cost estimate), scores each prediction deterministically, and writes
predictions_result.md.

Run:  python -m pipeline.compare_predictions
"""
from __future__ import annotations

import json
import os

PREDICTIONS = "predictions.json"
RESULT = "predictions_result.md"


def compare(predictions: dict) -> dict:
    """Score each prediction: hit/miss (numeric within 25%), recorded (text with an
    actual, for human judgement), or pending (unfilled / not yet measured)."""
    out = {}
    for key, v in predictions.get("predictions", {}).items():
        pred, act = v.get("predicted"), v.get("actual")
        unfilled = (act is None or pred is None
                    or (isinstance(pred, str) and pred.strip().startswith("<FILL")))
        if unfilled:
            verdict = "pending"
        elif isinstance(pred, (int, float)) and isinstance(act, (int, float)):
            tol = 0.25 * (abs(pred) or 1)
            verdict = "hit" if abs(pred - act) <= tol else "miss"
        else:
            verdict = "recorded"        # text prediction — a human judges the match
        out[key] = {"predicted": pred, "actual": act, "verdict": verdict}
    return out


def gather_actuals(dataset_path: str = "data/final/dataset.csv",
                   cost_per_llm_call_usd: float = 0.0,
                   calls_per_record: float = 3.0) -> dict:
    """Measurable actuals. Cost is $0 on the free tier; the meaningful figure is
    the per-record LLM-call load, scaled by whatever $/call you plug in."""
    try:
        with open(dataset_path, encoding="utf-8") as f:
            qualified = max(sum(1 for _ in f) - 1, 0)
    except OSError:
        qualified = 0
    per_record = round(calls_per_record * cost_per_llm_call_usd, 6)
    return {
        "qualified_records": qualified,
        "cost_to_refresh_one_record_usd": per_record,
        "cost_to_refresh_all_500_usd": round(per_record * 500, 6),
    }


def main() -> str:
    preds = json.load(open(PREDICTIONS, encoding="utf-8"))
    actuals = gather_actuals()
    # fill measurable actuals into the predictions before scoring
    for key, val in actuals.items():
        if key in preds.get("predictions", {}) and preds["predictions"][key].get("actual") is None:
            preds["predictions"][key]["actual"] = val
    scored = compare(preds)

    lines = ["# Predictions vs actual", "",
             f"_Predictions made: {preds.get('made_on', '?')}. "
             f"Qualified records: {actuals['qualified_records']}._", "",
             "| Prediction | Predicted | Actual | Verdict |", "|---|---|---|---|"]
    for key, r in scored.items():
        lines.append(f"| {key} | {r['predicted']} | {r['actual']} | **{r['verdict']}** |")
    lines += ["", "_pending = not yet filled/measured; recorded = text prediction, "
              "judge by hand; hit/miss = numeric within 25%._"]
    with open(RESULT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[predictions] wrote {RESULT} ({len(scored)} predictions)")
    return RESULT


if __name__ == "__main__":
    main()
