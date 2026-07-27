import os

import pytest

from rag import llm


def _both_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("NVIDIA_API_KEY", "n")


def test_falls_over_to_nvidia_when_groq_fails(monkeypatch):
    _both_keys(monkeypatch)
    seen = []

    def fake_call(provider, system, user, temperature):
        seen.append(provider[0])
        if provider[0] == "groq":
            raise RuntimeError("groq down")
        return "answer from nvidia"

    monkeypatch.setattr(llm, "_call", fake_call)
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    out = llm.chat("sys", "user")
    assert out == "answer from nvidia"
    assert "groq" in seen and "nvidia" in seen  # tried groq first, then nvidia


def test_raises_only_when_all_providers_fail(monkeypatch):
    _both_keys(monkeypatch)
    monkeypatch.setattr(llm, "_call",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")


def test_no_keys_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        llm.chat("s", "u")
