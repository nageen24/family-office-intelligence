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


def test_root_serves_search_page():
    c = TestClient(api.app)
    r = c.get("/")
    assert r.status_code == 200
    assert 'id="q"' in r.text            # the search input is present
    assert '/static/search.js' in r.text
    assert 'href="/agent"' in r.text     # link to the Agent page


def test_agent_page_is_a_separate_link():
    c = TestClient(api.app)
    r = c.get("/agent")
    assert r.status_code == 200
    assert 'id="goal"' in r.text         # the agent's own goal box
    assert '/static/agent.js' in r.text
    assert 'href="/"' in r.text          # link back to Search


def test_corpus_endpoint_reports_type_breakdown():
    c = TestClient(api.app)
    d = c.get("/corpus").json()
    assert d["total"] == d["mfo"] + d["sfo"] + d["unconfirmed"]
