"""API layer: FastAPI backend exposing the RAG. Separate from data/retrieval/
answer (presentation talks only to this). Deployable (uvicorn), not a notebook.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.answer import answer

app = FastAPI(title="Family Office Intelligence")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)


class Query(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/answer")
def answer_endpoint(q: Query):
    try:
        return answer(q.query)
    except Exception:
        # never leak an error dump to the customer layer
        return {"text": "Something went wrong on our side. Please try again.",
                "verdict": "declined", "sources": []}
