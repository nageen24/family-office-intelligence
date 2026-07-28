from rag.retrieve import retrieve


def test_relevant_query_returns_hits():
    r = retrieve("family offices in New York")
    assert r["hits"]
    assert r["gated"] is False


def test_nonsense_query_is_gated():
    r = retrieve("how do I bake sourdough bread at home", min_score=0.35)
    assert r["gated"] is True


def test_named_firm_is_injected_even_if_semantics_miss():
    # A firm named outright must reach the LLM regardless of embedding score,
    # and its presence must lift the gate so we can answer honestly about it.
    r = retrieve("what is the email of Duquesne Family Office?")
    names = [h.get("firm_name") for h in r["hits"]]
    assert any("Duquesne" in (n or "") for n in names)
    assert r["gated"] is False
