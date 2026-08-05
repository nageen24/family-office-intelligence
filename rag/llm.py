"""LLM client with provider failover (the RAG's only keyed dependency).

Both LLM-1 (answerer) and LLM-2 (validator) call `chat()`, which tries providers
in order and falls over to the next if one is down/rate-limited:

  1. Groq (key 1) — primary; fast, free.
  2. Groq (key 2) — backup on an independent account; if key 1 errors or is
     rate-limited, the same call runs here instead.

Both use a llama-3.3-70b model, so behaviour stays consistent. Only if EVERY
configured provider fails does the caller get an error state. A provider with no
key configured is skipped. Keys live in .env (gitignored) / GitHub + Vercel
secrets. Groq isn't Google, so it dodges the IP-flag that blocked our search work.
"""
from __future__ import annotations

import os
from typing import List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# (name, endpoint, api-key env var, model id)
# Primary + backup are BOTH Groq (same fast llama-3.3-70b) on two independent
# accounts/keys, so one account's rate-limit or outage doesn't take answering
# down. The second key IS the redundancy; a provider with no key set is skipped.
GROQ = "https://api.groq.com/openai/v1/chat/completions"
PROVIDERS = [
    ("groq", GROQ, "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    ("groq-2", GROQ, "GROQ_API_KEY_2", "llama-3.3-70b-versatile"),
]


def _configured() -> List[tuple]:
    return [p for p in PROVIDERS if os.getenv(p[2])]


# A hosted answer runs against a hard serverless deadline (~60s), and both LLM-1
# and LLM-2 must fit inside it. So each provider gets a SHORT timeout and we fail
# straight over to the next one — a degraded primary must cost seconds, not the
# whole budget. The two independent providers ARE the redundancy; a slow inner
# retry on a stalling endpoint would just burn the deadline, so there isn't one.
_TIMEOUT = 18


def _call(provider: tuple, system: str, user: str, temperature: float,
          model: Optional[str] = None) -> str:
    name, endpoint, env, default_model = provider
    r = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {os.getenv(env)}"},
        json={"model": model or default_model, "temperature": temperature,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# Groq rate limits (TPM and TPD) are PER KEY, so alternating which key takes the
# next call doubles the usable budget instead of exhausting key 1 first and
# paying a failed round-trip on every overflow call. Failover is unchanged: the
# other key is still tried when the first one errors.
_rr_lock = __import__("threading").Lock()
_rr = [0]


def chat(system: str, user: str, temperature: float = 0.0,
         model: Optional[str] = None) -> str:
    """`model` overrides each provider's default (e.g. a smaller model for bulk
    extraction, whose per-model daily token budget is separate)."""
    providers = _configured()
    if not providers:
        raise RuntimeError("No LLM provider key set (GROQ_API_KEY / GROQ_API_KEY_2)")
    with _rr_lock:
        start = _rr[0] % len(providers)
        _rr[0] += 1
    last: Optional[Exception] = None
    for provider in providers[start:] + providers[:start]:  # next key first, rest = fallback
        try:
            return _call(provider, system, user, temperature, model)
        except Exception as e:
            last = e
    raise last
