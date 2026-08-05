import pytest

from rag import llm


def _both_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY_2", "g2")
    for e in ("CEREBRAS_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(e, raising=False)


def test_falls_over_to_second_provider_when_first_fails(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_rr", [0])        # deterministic: provider 1 first
    seen = []

    def fake_call(provider, system, user, temperature, small=False, model=None):
        seen.append(provider["name"])
        if provider["name"] == "groq":
            raise RuntimeError("groq key 1 down")
        return "answer from backup"

    monkeypatch.setattr(llm, "_call", fake_call)
    assert llm.chat("sys", "user") == "answer from backup"
    assert "groq" in seen and "groq-2" in seen  # tried first, then next


def test_round_robin_alternates_and_passes_small_tier(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_rr", [0])
    seen = []

    def fake_call(provider, system, user, temperature, small=False, model=None):
        seen.append((provider["name"], small))
        return "ok"

    monkeypatch.setattr(llm, "_call", fake_call)
    llm.chat("s", "u", small=True)
    llm.chat("s", "u", small=True)
    assert [p for p, _ in seen] == ["groq", "groq-2"]   # per-provider budgets shared
    assert all(small for _, small in seen)


def test_round_robin_spans_all_configured_providers(monkeypatch):
    _both_keys(monkeypatch)
    for e in ("CEREBRAS_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(e, "k")
    monkeypatch.setattr(llm, "_rr", [0])
    seen = []
    monkeypatch.setattr(llm, "_call",
                        lambda p, *a, **k: seen.append(p["name"]) or "ok")
    for _ in range(4):
        llm.chat("s", "u", small=True)
    assert seen == ["groq", "groq-2", "cerebras", "gemini"]


def test_small_tier_selects_each_providers_own_small_model(monkeypatch):
    # the 'small' signal must map to each provider's OWN model id, not a shared one
    groq = next(p for p in llm.PROVIDERS if p["name"] == "groq")
    cerebras = next(p for p in llm.PROVIDERS if p["name"] == "cerebras")
    assert llm._model_for(groq, small=True, override=None) == "llama-3.1-8b-instant"
    assert llm._model_for(cerebras, small=True, override=None) == "llama3.1-8b"
    assert llm._model_for(groq, small=False, override=None) == "llama-3.3-70b-versatile"
    assert llm._model_for(groq, small=True, override="x") == "x"


def test_gemini_uses_its_own_request_shape(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "hi there"}]}}]}

    def fake_post(url, params=None, json=None, timeout=None, headers=None):
        captured.update(url=url, params=params, json=json)
        return _Resp()

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setenv("GEMINI_API_KEY", "gk")
    gem = next(p for p in llm.PROVIDERS if p["name"] == "gemini")
    out = llm._call(gem, "SYS", "USER", 0.0, small=True)
    assert out == "hi there"
    assert captured["url"].endswith("gemini-2.0-flash-lite:generateContent")
    assert captured["params"] == {"key": "gk"}
    assert captured["json"]["system_instruction"]["parts"][0]["text"] == "SYS"
    assert captured["json"]["contents"][0]["parts"][0]["text"] == "USER"


def test_raises_only_when_all_providers_fail(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_call",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")


def test_no_keys_raises(monkeypatch):
    for e in ("GROQ_API_KEY", "GROQ_API_KEY_2", "CEREBRAS_API_KEY",
              "GEMINI_API_KEY"):
        monkeypatch.delenv(e, raising=False)
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")
