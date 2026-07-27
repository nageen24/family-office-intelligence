"""Retrieval layer: structured filter + semantic search + score gate.

Hybrid, as the assessment requires: a keyword-driven structured filter narrows
the set (firm type, has-email), then semantic similarity ranks within it. The
score gate is the cheap first guard of the grounding control — if nothing scores
high enough, the caller should decline rather than answer from weak matches.
"""
from __future__ import annotations

from functools import lru_cache

from rag.embed import embed_one

COLLECTION = "firms"


@lru_cache(maxsize=1)
def _client():
    """In-memory Qdrant built once per process from the dataset.

    In-memory (not the local file store) so a web server can hold it without the
    single-process file lock, and so deploy needs no external vector DB — the
    66 vectors are rebuilt at startup in ~a second.
    """
    from qdrant_client import QdrantClient
    from rag.ingest import build_index
    client = QdrantClient(":memory:")
    build_index(client)
    return client


def _filters(query: str):
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    q = query.lower()
    conds = []
    if "single family" in q or "single-family" in q or " sfo" in q or q.startswith("sfo"):
        conds.append(FieldCondition(key="firm_type", match=MatchValue(value="SFO")))
    elif "multi family" in q or "multi-family" in q or "mfo" in q:
        conds.append(FieldCondition(key="firm_type", match=MatchValue(value="MFO")))
    if "email" in q:
        conds.append(FieldCondition(key="has_email", match=MatchValue(value=True)))
    return Filter(must=conds) if conds else None


def retrieve(query: str, k: int = 8, min_score: float = 0.25) -> dict:
    """Return {"hits": [payload...], "top_score": float, "gated": bool}.

    gated=True means nothing cleared the score gate — the answer layer should
    decline instead of answering from weak evidence.
    """
    vec = embed_one(query)
    res = _client().query_points(
        COLLECTION, query=vec, query_filter=_filters(query), limit=k).points
    hits = [p.payload for p in res]
    top = float(res[0].score) if res else 0.0
    return {"hits": hits, "top_score": top, "gated": (not res) or top < min_score}
