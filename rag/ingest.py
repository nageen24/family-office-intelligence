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
    """Human-readable prose per firm — this is the text embedded AND handed to
    the answer LLM, so it must carry every high-value cell the CSV holds
    (especially the contact intel), or the RAG can't answer questions about it.
    """
    parts = [f"{row['firm_name']} is a family office "
             f"(type: {row.get('firm_type') or 'Unconfirmed'})."]
    if row.get("hq_location"):
        parts.append(f"Located at {row['hq_location']}.")
    if row.get("aum"):
        parts.append(f"Reported AUM: {row['aum']}.")
    if row.get("principal_name"):
        parts.append(f"Principal / key contact: {row['principal_name']}.")
    if row.get("principal_title"):
        parts.append(f"Contact title: {row['principal_title']}.")
    if row.get("principal_phone"):
        parts.append(f"Phone: {row['principal_phone']}.")
    if row.get("principal_email"):
        parts.append(f"Email: {row['principal_email']}.")
    if row.get("website"):
        parts.append(f"Website: {row['website']}.")
    if row.get("corporate_linkedin"):
        parts.append(f"LinkedIn: {row['corporate_linkedin']}.")
    if row.get("investing_thesis"):
        parts.append(f"Investing focus: {row['investing_thesis']}.")
    if row.get("mandate"):
        parts.append(f"Investing mandate: {row['mandate']}.")
    if row.get("background"):
        parts.append(f"Background: {row['background']}.")
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


def build_index(client, csv_path: str = "data/final/dataset.csv",
                collection: str = "firms") -> int:
    """Populate any Qdrant client (file, memory, or server) from the dataset.

    Shared by the persistent ingest and the in-memory server path so the index
    is built the same way everywhere.
    """
    from qdrant_client.models import Distance, VectorParams, PointStruct
    from rag.embed import embed

    rows: List[dict] = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    blurbs = [record_to_blurb(r) for r in rows]
    vecs = embed(blurbs)  # (n, dim) L2-normalized

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


def ingest(csv_path: str = "data/final/dataset.csv",
           qdrant_path: str = "data/rag/qdrant",
           collection: str = "firms") -> int:
    """Persistent build to a local Qdrant folder (for inspection/dev)."""
    from qdrant_client import QdrantClient
    client = QdrantClient(path=qdrant_path)
    return build_index(client, csv_path, collection)


if __name__ == "__main__":
    print(f"ingested {ingest()} records")
