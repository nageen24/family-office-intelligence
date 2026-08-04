"""S22 — structured, full-corpus retrieval the Stage-1 semantic RAG couldn't do.

Multi-constraint filtering over the real structured fields (category, location,
investing focus, commercial tier, trust) that ALWAYS runs on the full corpus and
reports honest scope: how many were eligible, how many matched, how many shown,
and any constraint it could not honor (fix#8).
"""
from rag.structured import search, count, get_record

CORPUS = [
    {"firm_name": "Alpha MFO", "category": "MFO", "hq_location": "Dallas, TX",
     "investing_thesis": "healthcare and technology growth equity", "is_commercial": "True",
     "trust": "fresh"},
    {"firm_name": "Beta FO", "category": "FO-type-unknown", "hq_location": "Austin, TX",
     "investing_thesis": "real estate and private credit", "is_commercial": "False",
     "trust": "stale"},
    {"firm_name": "Gamma Family Offices", "category": "MFO", "hq_location": "New York, NY",
     "investing_thesis": "healthcare buyouts", "is_commercial": "True", "trust": "fresh"},
]


def test_search_filters_and_reports_full_corpus_scope():
    r = search(CORPUS, category="MFO", location="TX")
    assert r["eligible"] == 3                         # scope always over the full corpus
    assert r["matched"] == 1                          # only Alpha (MFO + TX)
    assert r["hits"][0]["firm_name"] == "Alpha MFO"
    assert r["unhonored"] == []


def test_search_focus_keyword_matches_thesis():
    r = search(CORPUS, focus="healthcare")
    assert {h["firm_name"] for h in r["hits"]} == {"Alpha MFO", "Gamma Family Offices"}


def test_search_reports_unhonored_constraint():
    r = search(CORPUS, aum_over=1_000_000_000)        # field we don't hold
    assert "aum_over" in r["unhonored"]
    assert r["matched"] == 3                          # constraint ignored, not silently applied


def test_search_shown_capped_by_limit_but_matched_is_true_total():
    r = search(CORPUS, category="MFO", limit=1)
    assert r["matched"] == 2                          # true total
    assert r["shown"] == 1                            # capped


def test_count_runs_on_full_corpus():
    assert count(CORPUS, is_commercial=True) == 2


def test_get_record_by_name():
    assert get_record(CORPUS, "gamma")["firm_name"] == "Gamma Family Offices"
    assert get_record(CORPUS, "nonexistent") is None
