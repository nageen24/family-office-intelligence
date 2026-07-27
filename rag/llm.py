"""Thin Groq chat client (the only keyed dependency in the RAG).

Groq was chosen for both LLMs because it is fast, free (no card), and — unlike
Google — unaffected by the IP-flag that blocked our earlier search work. Key
lives in .env (gitignored).
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


def chat(system: str, user: str, temperature: float = 0.0) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set in environment/.env")
    r = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL, "temperature": temperature,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
