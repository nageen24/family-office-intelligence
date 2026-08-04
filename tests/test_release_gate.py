"""Deterministic release gate — plain code, not the LLM, recomputes the counts
from the CSV and blocks any composed answer whose numbers don't match.

Catches the Stage-1 failure class ("we have 8 family offices" when there are 50)
and impossible counts (more than exist), before the answer reaches the user.
"""
from rag.release_gate import recompute_truth, release_gate

RECORDS = [{"category": "MFO"}, {"category": "MFO"}, {"category": "SFO"},
           {"category": "FO-type-unknown"}]     # total 4


def test_matching_total_passes():
    r = release_gate("We hold 4 verified family offices.", recompute_truth(RECORDS))
    assert r["ok"] and r["reason"] is None


def test_wrong_total_is_blocked():
    r = release_gate("Our dataset has 8 verified family offices.", recompute_truth(RECORDS))
    assert not r["ok"]
    assert "8" in r["reason"] and "4" in r["reason"]


def test_impossible_count_is_blocked():
    r = release_gate("There are 40 records matching your query.", recompute_truth(RECORDS))
    assert not r["ok"]                                   # 40 > 4 can't be true


def test_subset_claim_is_allowed():
    # "2 MFOs" is a legitimate subset, not a corpus-total claim
    assert release_gate("2 firms match: both are MFOs.", recompute_truth(RECORDS))["ok"]


def test_recompute_truth_counts_from_records():
    t = recompute_truth(RECORDS)
    assert t["total"] == 4 and t["by_category"]["MFO"] == 2
