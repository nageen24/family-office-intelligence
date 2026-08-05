"""LLM client with multi-provider round-robin + failover (the RAG's only keyed dep).

Both LLM-1 (answerer) and LLM-2 (validator) call `chat()`, and so does the climb's
bulk extraction (`small=True`). Every configured free provider takes turns:

  - groq / groq-2   two independent Groq accounts (llama-3.3-70b / -3.1-8b)
  - cerebras        Cerebras Cloud (OpenAI-compatible, high free daily limits)
  - gemini          Google Gemini free tier (its OWN request/response shape)

Rate limits (TPM and TPD) are PER PROVIDER, so round-robining the next call across
providers ADDS their daily budgets together instead of exhausting one first — this
is what multiplies the tokens-per-day ceiling the climb runs against. Failover is
preserved: if the chosen provider errors/rate-limits, the call runs on the next.

Only quotes that `ontology.quote_present` re-verifies become proof, so a different
or weaker model can only MISS a proof, never fabricate one — mixing providers is
safe for honesty by construction. A provider with no key set is skipped; if every
configured provider fails, the caller gets the last error. Keys live in .env /
GitHub + Vercel secrets.
"""
from __future__ import annotations

import os
import threading
from typing import List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS = "https://api.cerebras.ai/v1/chat/completions"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"

# Each provider: kind decides the request/response shape ("openai" vs "gemini");
# `big` is the 70b-class answer/validate model, `small` the fast bulk-extraction
# model. Each provider maps the SAME tier to its own correct model id, so the
# `small=True` signal works across providers that name models differently.
PROVIDERS = [
    {"name": "groq", "kind": "openai", "endpoint": GROQ, "env": "GROQ_API_KEY",
     "big": "llama-3.3-70b-versatile", "small": "llama-3.1-8b-instant"},
    {"name": "groq-2", "kind": "openai", "endpoint": GROQ, "env": "GROQ_API_KEY_2",
     "big": "llama-3.3-70b-versatile", "small": "llama-3.1-8b-instant"},
    {"name": "cerebras", "kind": "openai", "endpoint": CEREBRAS,
     "env": "CEREBRAS_API_KEY", "big": "llama-3.3-70b", "small": "llama3.1-8b"},
    {"name": "gemini", "kind": "gemini", "endpoint": GEMINI, "env": "GEMINI_API_KEY",
     "big": "gemini-2.0-flash", "small": "gemini-2.0-flash-lite"},
]


def _configured() -> List[dict]:
    return [p for p in PROVIDERS if os.getenv(p["env"])]


def provider_count() -> int:
    """How many free LLM providers currently have a key set. The climb scales
    its batch size and call spacing off this — daily budgets are per provider."""
    return len(_configured())


# A hosted answer runs against a hard serverless deadline (~60s), and both LLM-1
# and LLM-2 must fit inside it. Each provider gets a SHORT timeout and we fail
# straight over — a degraded provider costs seconds, not the whole budget. The
# other providers ARE the redundancy, so there's no slow inner retry.
_TIMEOUT = 18


def _model_for(provider: dict, small: bool, override: Optional[str]) -> str:
    if override:
        return override
    return provider["small"] if small else provider["big"]


def _call_openai(provider: dict, system: str, user: str, temperature: float,
                 model: str) -> str:
    r = requests.post(
        provider["endpoint"],
        headers={"Authorization": f"Bearer {os.getenv(provider['env'])}"},
        json={"model": model, "temperature": temperature,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _call_gemini(provider: dict, system: str, user: str, temperature: float,
                 model: str) -> str:
    url = f"{provider['endpoint']}/{model}:generateContent"
    r = requests.post(
        url,
        params={"key": os.getenv(provider["env"])},
        json={"system_instruction": {"parts": [{"text": system}]},
              "contents": [{"role": "user", "parts": [{"text": user}]}],
              "generationConfig": {"temperature": temperature}},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    cands = (r.json() or {}).get("candidates") or []
    if not cands:
        raise RuntimeError("gemini returned no candidates")
    parts = (cands[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def _call(provider: dict, system: str, user: str, temperature: float,
          small: bool = False, model: Optional[str] = None) -> str:
    m = _model_for(provider, small, model)
    if provider["kind"] == "gemini":
        return _call_gemini(provider, system, user, temperature, m)
    return _call_openai(provider, system, user, temperature, m)


# Round-robin cursor: alternate which provider takes the NEXT call so per-provider
# daily budgets add up instead of draining one first.
_rr_lock = threading.Lock()
_rr = [0]


def chat(system: str, user: str, temperature: float = 0.0,
         small: bool = False, model: Optional[str] = None) -> str:
    """Round-robin across configured providers with failover.

    small=True selects each provider's fast bulk-extraction model (the climb path);
    the RAG answerer/validator leave it False for the 70b-class model. `model`
    forces a specific id on every provider (mainly for tests)."""
    providers = _configured()
    if not providers:
        raise RuntimeError("No LLM provider key set "
                           "(GROQ_API_KEY / CEREBRAS_API_KEY / GEMINI_API_KEY)")
    with _rr_lock:
        start = _rr[0] % len(providers)
        _rr[0] += 1
    last: Optional[Exception] = None
    for provider in providers[start:] + providers[:start]:  # chosen first, rest = fallback
        try:
            return _call(provider, system, user, temperature, small=small,
                         model=model)
        except Exception as e:
            last = e
    raise last
