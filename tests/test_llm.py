import os

import pytest

from rag import llm


def _both_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")


def test_falls_over_to_backup_when_groq_fails(monkeypatch):
    _both_keys(monkeypatch)
    seen = []

    def fake_call(provider, system, user, temperature):
        seen.append(provider[0])
        if provider[0] == "groq":
            raise RuntimeError("groq down")
        return "answer from backup"

    monkeypatch.setattr(llm, "_call", fake_call)
    out = llm.chat("sys", "user")
    assert out == "answer from backup"
    assert "groq" in seen and "openrouter" in seen  # tried groq first, then backup


def test_raises_only_when_all_providers_fail(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_call",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")


def test_no_keys_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")
