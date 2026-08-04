from rag.retrieve import retrieve


def test_relevant_query_returns_hits():
    r = retrieve("family offices in New York")
    assert r["hits"]
    assert r["gated"] is False


def test_nonsense_query_is_gated():
    r = retrieve("how do I bake sourdough bread at home", min_score=0.35)
    assert r["gated"] is True


def test_type_query_includes_confirmed_and_unconfirmed():
    # A multi-family query must surface both the confirmed MFOs and the
    # Unconfirmed firms (the answer layer splits them into two sections), and
    # must NOT leak any confirmed single-family office.
    r = retrieve("list all multi family offices", k=100)
    types = {h.get("firm_type") for h in r["hits"]}
    assert "MFO" in types
    assert "Unconfirmed" in types
    assert "SFO" not in types


def test_multifamily_one_word_still_filters():
    # "multifamily" (one word) must filter the same as "multi family".
    spaced = {h["firm_name"] for h in retrieve("multi family offices", k=100)["hits"]}
    oneword = {h["firm_name"] for h in retrieve("multifamily offices", k=100)["hits"]}
    assert spaced == oneword


def test_named_firm_is_injected_even_if_semantics_miss():
    # A firm named outright must reach the LLM regardless of embedding score,
    # and its presence must lift the gate so we can answer honestly about it.
    # Data-agnostic: use a real firm from whichever dataset is currently served.
    import csv
    from rag.ingest import default_csv
    rows = list(csv.DictReader(open(default_csv(), encoding="utf-8")))
    assert rows, "served dataset is empty"
    firm = rows[0]["firm_name"]
    r = retrieve(f"what is the email of {firm}?")
    names = [h.get("firm_name") for h in r["hits"]]
    assert any(firm.split()[0] in (n or "") for n in names)
    assert r["gated"] is False
