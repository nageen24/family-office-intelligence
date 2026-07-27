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


@app.post("/answer")
def answer_endpoint(q: Query):
    try:
        return answer(q.query)
    except Exception:
        # never leak an error dump to the customer layer
        return {"text": "Something went wrong on our side. Please try again.",
                "verdict": "declined", "sources": []}
