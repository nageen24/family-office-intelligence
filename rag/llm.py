"""LLM client with provider failover (the RAG's only keyed dependency).

Both LLM-1 (answerer) and LLM-2 (validator) call `chat()`, which tries providers
in order and falls over to the next if one is down/rate-limited:

  1. Groq          — primary; fast, free.
  2. NVIDIA NIM    — backup; if Groq errors, the same call runs here instead.

Both are OpenAI-compatible and use a llama-3.3-70b model, so the answer behaviour
stays consistent across providers. Only if EVERY configured provider fails does
the caller get an error state. Providers with no key configured are skipped.
Keys live in .env (gitignored). Neither is Google, so both dodge the IP-flag that
blocked our earlier search work.
"""
from __future__ import annotations

import os
import time
from typing import List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# (name, endpoint, api-key env var, model id)
PROVIDERS = [
    ("groq", "https://api.groq.com/openai/v1/chat/completions",
     "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    ("nvidia", "https://integrate.api.nvidia.com/v1/chat/completions",
     "NVIDIA_API_KEY", "meta/llama-3.3-70b-instruct"),
]


def _configured() -> List[tuple]:
    return [p for p in PROVIDERS if os.getenv(p[2])]


def _call(provider: tuple, system: str, user: str, temperature: float) -> str:
    name, endpoint, env, model = provider
    r = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {os.getenv(env)}"},
        json={"model": model, "temperature": temperature,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def chat(system: str, user: str, temperature: float = 0.0) -> str:
    providers = _configured()
    if not providers:
        raise RuntimeError("No LLM provider key set (GROQ_API_KEY / NVIDIA_API_KEY)")
    last: Optional[Exception] = None
    for provider in providers:
        for attempt in range(2):  # one retry per provider on a transient blip
            try:
                return _call(provider, system, user, temperature)
            except Exception as e:
                last = e
                if attempt == 0:
                    time.sleep(1.0)
        # provider exhausted -> fall through to the next provider
    raise last
