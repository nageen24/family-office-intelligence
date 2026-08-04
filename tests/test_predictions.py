"""Prediction tracker — compares the user's 3 Day-2 predictions vs actual.

The user writes the 'predicted' values; the comparison is deterministic: numeric
predictions are hit/miss within tolerance, text predictions are 'recorded' for
human judgement, and anything not yet measured is 'pending'.
"""
from pipeline.compare_predictions import compare


def _preds(**kw):
    return {"predictions": kw}


def test_numeric_within_tolerance_is_a_hit():
    r = compare(_preds(cost={"predicted": 0.10, "actual": 0.11}))
    assert r["cost"]["verdict"] == "hit"


def test_numeric_far_off_is_a_miss():
    r = compare(_preds(cost={"predicted": 0.10, "actual": 0.50}))
    assert r["cost"]["verdict"] == "miss"


def test_unfilled_or_unmeasured_is_pending():
    r = compare(_preds(
        breaks={"predicted": "<FILL: your prediction>", "actual": None},
        goal2={"predicted": "high on 2 firms", "actual": None}))
    assert r["breaks"]["verdict"] == "pending"
    assert r["goal2"]["verdict"] == "pending"


def test_text_prediction_with_actual_is_recorded_for_review():
    r = compare(_preds(breaks={"predicted": "Groq rate limits", "actual": "reach wall"}))
    assert r["breaks"]["verdict"] == "recorded"
