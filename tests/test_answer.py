from rag import answer as A


def test_declines_when_gated(monkeypatch):
    monkeypatch.setattr(A, "retrieve",
                        lambda q, **k: {"hits": [], "top_score": 0.0, "gated": True})
    r = A.answer("something unrelated")
    assert r["verdict"] == "declined"
    assert "confident" in r["text"].lower()


def test_validator_can_force_decline(monkeypatch):
    monkeypatch.setattr(A, "retrieve", lambda q, **k: {
        "hits": [{"firm_name": "X", "blurb": "X is a family office."}],
        "top_score": 0.9, "gated": False})
    calls = iter(["The email is a@x.com.",
                  "DECLINE: the records contain no email for X."])
    monkeypatch.setattr(A, "_chat", lambda *a, **k: next(calls))
    r = A.answer("what is X's email?")
    assert r["verdict"] == "declined"


def test_approve_passes_draft_through(monkeypatch):
    monkeypatch.setattr(A, "retrieve", lambda q, **k: {
        "hits": [{"firm_name": "X", "blurb": "X is a family office in NY."}],
        "top_score": 0.9, "gated": False})
    calls = iter(["X is a family office located in New York.", "APPROVE"])
    monkeypatch.setattr(A, "_chat", lambda *a, **k: next(calls))
    r = A.answer("where is X?")
    assert r["verdict"] == "approved"
    assert "New York" in r["text"]
    assert r["sources"] == ["X"]
