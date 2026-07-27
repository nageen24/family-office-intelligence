"""Ingest layer: dataset records -> readable blurb + filter metadata -> local
embeddings -> Qdrant. Run once; the query path only re-embeds the user's query.

Kept deliberately separate from retrieval/answer/presentation (assessment
requires layer separation). Embeddings are LOCAL via model2vec (a distilled
static embedding that runs on pure NumPy) — chosen after torch/onnxruntime both
failed to load on this Python 3.14 / Windows box (DLL init errors). model2vec
has no native ML runtime, so it works in dev and on the Linux deploy target, is
keyless, and can't be IP-blocked. See DECISIONS.md 2026-07-28.
"""
from __future__ import annotations

import csv
from typing import List


def record_to_blurb(row: dict) -> str:
    """Human-readable prose per firm — this is what gets embedded/searched."""
    parts = [f"{row['firm_name']} is a family office "
             f"(type: {row.get('firm_type') or 'Unconfirmed'})."]
    if row.get("hq_location"):
        parts.append(f"Located in {row['hq_location']}.")
    if row.get("aum"):
        parts.append(f"Reported AUM: {row['aum']}.")
    if row.get("principal_name"):
        parts.append(f"Principal: {row['principal_name']}.")
    if row.get("principal_title"):
        parts.append(f"Key contact title: {row['principal_title']}.")
    if row.get("investing_thesis"):
        parts.append(f"Investing focus: {row['investing_thesis']}.")
    if row.get("recent_signal"):
        parts.append(f"Recent activity: {row['recent_signal']}.")
    return " ".join(parts)


def build_metadata(row: dict) -> dict:
    """Structured fields for exact filtering in the retrieval layer."""
    return {
        "firm_name": row["firm_name"],
        "firm_type": row.get("firm_type") or "Unconfirmed",
        "location": row.get("hq_location") or "",
        "has_email": bool(row.get("principal_email")),
        "has_phone": bool(row.get("principal_phone")),
        "has_aum": bool(row.get("aum")),
        "has_signal": bool(row.get("recent_signal")),
    }


def ingest(csv_path: str = "data/final/dataset.csv",
           qdrant_path: str = "data/rag/qdrant",
           collection: str = "firms") -> int:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    from rag.embed import embed

    rows: List[dict] = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    blurbs = [record_to_blurb(r) for r in rows]
    vecs = embed(blurbs)  # (n, dim) L2-normalized

    client = QdrantClient(path=qdrant_path)
    client.recreate_collection(
        collection,
        vectors_config=VectorParams(size=vecs.shape[1], distance=Distance.COSINE),
    )
    points = [
        PointStruct(id=i, vector=vecs[i].tolist(),
                    payload={**rows[i], **build_metadata(rows[i]), "blurb": blurbs[i]})
        for i in range(len(rows))
    ]
    client.upsert(collection, points)
    return len(points)


if __name__ == "__main__":
    print(f"ingested {ingest()} records")
