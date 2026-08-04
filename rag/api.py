"""API layer: FastAPI backend exposing the RAG. Separate from data/retrieval/
answer (presentation talks only to this). Deployable (uvicorn), not a notebook.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag.answer import answer

app = FastAPI(title="Family Office Intelligence")

# S22-S24: the paid-tier surfaces — structured full-corpus search + the bounded
# agent, both returned through the 5-state product language with honest scope.
from dataclasses import asdict  # noqa: E402
from rag.structured import load_records, search  # noqa: E402
from rag.product import respond  # noqa: E402
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

_FE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=_FE), name="static")


class Query(BaseModel):
    query: str


@app.get("/")
def root():
    return FileResponse(os.path.join(_FE, "index.html"))


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/corpus")
def corpus():
    """Live corpus size + firm-type breakdown for the header (no hard-coded numbers)."""
    from collections import Counter
    recs = load_records()
    c = Counter((r.get("firm_type") or "Unconfirmed") for r in recs)
    return {"total": len(recs), "mfo": c.get("MFO", 0),
            "sfo": c.get("SFO", 0), "unconfirmed": c.get("Unconfirmed", 0)}


@app.post("/answer")
def answer_endpoint(q: Query):
    try:
        return answer(q.query)
    except Exception:
        # never leak an error dump to the customer layer
        return {"text": "Something went wrong on our side. Please try again.",
                "verdict": "declined", "sources": []}


class SearchQuery(BaseModel):
    category: str | None = None
    location: str | None = None
    focus: str | None = None
    is_commercial: bool | None = None
    min_trust: str | None = None
    limit: int | None = 25
    aum_over: float | None = None       # deliberately unsupported -> reported as unhonored


@app.post("/search")
def search_endpoint(q: SearchQuery):
    """S22/S24 — structured full-corpus search, returned in the 5-state language."""
    try:
        records = load_records()
        result = search(records, **{k: v for k, v in q.model_dump().items() if v is not None})
        return respond(result)
    except Exception as e:
        return respond({"error": str(e)})


class Goal(BaseModel):
    goal: str
    budget: int | None = 6


@app.post("/agent")
def agent_endpoint(g: Goal):
    """S23/S24 — the bounded agent: worker + independent release authority, returned
    in the 5-state language with scope. Weak evidence -> honest 'declined'."""
    try:
        from rag.agent import answer_goal
        st = answer_goal(g.goal, budget=g.budget or 6)
        payload = asdict(st)
        payload["eligible"] = len(load_records())
        return respond(payload)
    except Exception as e:
        return respond({"error": str(e)})
