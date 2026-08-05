import os

import pytest

from rag import llm


def _both_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY_2", "g2")


def test_falls_over_to_second_groq_key_when_first_fails(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_rr", [0])        # deterministic: key 1 goes first
    seen = []

    def fake_call(provider, system, user, temperature, model=None):
        seen.append(provider[0])
        if provider[0] == "groq":
            raise RuntimeError("groq key 1 down")
        return "answer from backup"

    monkeypatch.setattr(llm, "_call", fake_call)
    out = llm.chat("sys", "user")
    assert out == "answer from backup"
    assert "groq" in seen and "groq-2" in seen  # tried key 1 first, then key 2


def test_round_robin_alternates_keys_and_passes_model(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_rr", [0])
    seen = []

    def fake_call(provider, system, user, temperature, model=None):
        seen.append((provider[0], model))
        return "ok"

    monkeypatch.setattr(llm, "_call", fake_call)
    llm.chat("s", "u", model="llama-3.1-8b-instant")
    llm.chat("s", "u", model="llama-3.1-8b-instant")
    assert [p for p, _ in seen] == ["groq", "groq-2"]   # per-key budgets shared
    assert all(m == "llama-3.1-8b-instant" for _, m in seen)


def test_raises_only_when_all_providers_fail(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_call",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")


def test_no_keys_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")
