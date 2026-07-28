"""Retrieval layer: structured filter + semantic search + score gate.

Hybrid, as the assessment requires: a keyword-driven structured filter narrows
the set (firm type, has-email), then semantic similarity ranks within it. The
score gate is the cheap first guard of the grounding control — if nothing scores
high enough, the caller should decline rather than answer from weak matches.
"""
from __future__ import annotations

import re
from functools import lru_cache

from rag.embed import embed_one

COLLECTION = "firms"

# Generic words shared by most firm names — stripped so name-matching keys on the
# distinctive part ("Duquesne"), not the boilerplate every firm shares.
_NAME_STOP = {"family", "office", "offices", "llc", "lp", "ltd", "inc", "llp",
              "the", "and", "co", "group", "capital", "partners", "services",
              "trust", "ag", "advisors", "management", "wealth"}


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


@lru_cache(maxsize=1)
def _corpus():
    """Every firm payload, fetched once — the index for lexical name matching.

    Semantic top-k alone misses a firm the user names outright (a weak static
    embedding barely moves for a proper noun like 'Duquesne'), so a named firm
    would never reach the LLM. This lets us inject the exact record by name.
    """
    pts = _client().scroll(COLLECTION, limit=100000,
                           with_payload=True, with_vectors=False)[0]
    return [(p.id, (p.payload.get("firm_name") or "")) for p in pts]


def _name_matches(query: str) -> list:
    """Point-ids of firms the query names explicitly.

    A firm matches when ALL its distinctive name tokens (generic words stripped)
    appear in the query — so 'email of Duquesne Family Office' matches Duquesne,
    but a bare 'family office' matches nothing.
    """
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    ids = []
    for pid, name in _corpus():
        toks = [t for t in re.findall(r"[a-z0-9]+", name.lower())
                if t not in _NAME_STOP and len(t) > 2]
        if toks and all(t in q for t in toks):
            ids.append(pid)
    return ids


def is_single_query(q: str) -> bool:
    q = q.lower()
    return ("single family" in q or "single-family" in q or " sfo" in q
            or q.startswith("sfo"))


def is_multi_query(q: str) -> bool:
    q = q.lower()
    return ("multi family" in q or "multi-family" in q or "multifamily" in q
            or " mfo" in q or q.startswith("mfo"))


def _filters(query: str):
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
    q = query.lower()
    conds = []
    # A type question returns the CONFIRMED firms of that type PLUS the
    # Unconfirmed ones (verified firms whose single-vs-multi label isn't proven).
    # The answer layer renders them as two sections; here we just make sure both
    # sets reach the LLM. Single-family markers are checked first because
    # "single-family" also contains "family".
    if is_single_query(q):
        conds.append(FieldCondition(key="firm_type",
                                    match=MatchAny(any=["SFO", "Unconfirmed"])))
    elif is_multi_query(q):
        conds.append(FieldCondition(key="firm_type",
                                    match=MatchAny(any=["MFO", "Unconfirmed"])))
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
    gated = (not res) or top < min_score

    # Inject any firm the query names outright but semantic search missed. A named
    # firm is strong evidence, so its presence lifts the score gate — the LLM can
    # then answer honestly (even "we hold that firm but have no email on file"),
    # instead of a misleading blanket decline for a firm we actually have.
    named_ids = _name_matches(query)
    if named_ids:
        seen = {h.get("firm_name") for h in hits}
        named = _client().retrieve(COLLECTION, ids=named_ids[:5], with_payload=True)
        inject = [p.payload for p in named if p.payload.get("firm_name") not in seen]
        if inject:
            hits = inject + hits
            gated = False

    return {"hits": hits, "top_score": top, "gated": gated}
