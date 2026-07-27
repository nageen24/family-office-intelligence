"""Shared local embedding — model2vec static model on pure NumPy.

One loader used by both ingest and retrieve so the model is loaded once and the
query is embedded the same way the records were. No torch/onnx, no key, no
network at query time.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np

MODEL_NAME = "minishlab/potion-base-8M"


@lru_cache(maxsize=1)
def _model():
    from model2vec import StaticModel
    return StaticModel.from_pretrained(MODEL_NAME)


def embed(texts: List[str]) -> np.ndarray:
    """Return an (n, dim) float32 array of L2-normalized embeddings."""
    vecs = _model().encode(list(texts)).astype("float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def embed_one(text: str) -> List[float]:
    return embed([text])[0].tolist()
