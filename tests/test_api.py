from fastapi.testclient import TestClient

from rag import api


def test_health():
    c = TestClient(api.app)
    assert c.get("/health").json()["ok"] is True


def test_answer_endpoint(monkeypatch):
    monkeypatch.setattr(api, "answer",
                        lambda q: {"text": "hi", "verdict": "approved", "sources": ["X"]})
    c = TestClient(api.app)
    r = c.post("/answer", json={"query": "q"})
    assert r.status_code == 200
    assert r.json()["verdict"] == "approved"
    assert r.json()["sources"] == ["X"]
