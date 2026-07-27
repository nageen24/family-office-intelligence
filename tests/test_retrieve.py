from rag.retrieve import retrieve


def test_relevant_query_returns_hits():
    r = retrieve("family offices in New York")
    assert r["hits"]
    assert r["gated"] is False


def test_nonsense_query_is_gated():
    r = retrieve("how do I bake sourdough bread at home", min_score=0.35)
    assert r["gated"] is True
